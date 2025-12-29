"""
NeoSync License Manager
=======================

Simple license key validation system.
Supports offline validation with pre-generated keys.
"""

import os
import json
import hashlib
import secrets
import string
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict
import platform


@dataclass
class LicenseInfo:
    """License information"""
    license_key: str
    activation_date: str
    machine_id: str
    license_type: str  # 'pro', 'team', 'enterprise'
    expires: Optional[str] = None
    max_clips: int = 500
    features: List[str] = None

    def __post_init__(self):
        if self.features is None:
            self.features = ['all']


class LicenseManager:
    """
    Manage NeoSync licenses

    License key format: NEOS-XXXX-XXXX-XXXX-XXXX
    """

    LICENSE_FILE = ".neosync_license"
    VALID_PREFIXES = ["NEOS", "NEOFOX", "TEAM"]

    def __init__(self):
        self._license: Optional[LicenseInfo] = None
        self._valid_keys: set = set()
        self._load_valid_keys()

    def _get_license_path(self) -> Path:
        """Get path to license file"""
        if platform.system() == "Windows":
            app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
            return Path(app_data) / "NeoSync" / self.LICENSE_FILE
        else:
            return Path.home() / ".config" / "neosync" / self.LICENSE_FILE

    def _get_machine_id(self) -> str:
        """Generate unique machine identifier"""
        import uuid

        # Get various system identifiers
        identifiers = []

        # Platform info
        identifiers.append(platform.node())
        identifiers.append(platform.machine())
        identifiers.append(platform.processor())

        # Try to get MAC address
        try:
            mac = uuid.getnode()
            identifiers.append(str(mac))
        except:
            pass

        # Hash everything
        combined = "|".join(identifiers)
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    def _load_valid_keys(self):
        """Load pre-generated valid license keys"""
        # These are the 500 pre-generated valid keys
        # In production, this would be loaded from a secure source
        self._valid_keys = self._generate_key_set()

    def _generate_key_set(self) -> set:
        """Generate the set of valid license keys"""
        # Use a fixed seed for reproducible keys
        import random
        random.seed("NeoSync_NeoFox_2024_License_Keys")

        keys = set()
        chars = string.ascii_uppercase + string.digits

        prefixes = ["NEOS", "NEOFOX", "TEAM"]

        for i in range(500):
            prefix = prefixes[i % 3]
            parts = [prefix]

            for _ in range(4):
                part = ''.join(random.choices(chars, k=4))
                parts.append(part)

            key = '-'.join(parts)
            keys.add(key)

        return keys

    def generate_new_keys(self, count: int = 100, prefix: str = "NEOS") -> List[str]:
        """Generate new random license keys (for admin use)"""
        keys = []
        chars = string.ascii_uppercase + string.digits

        for _ in range(count):
            parts = [prefix]
            for _ in range(4):
                part = ''.join(secrets.choice(chars) for _ in range(4))
                parts.append(part)
            key = '-'.join(parts)
            keys.append(key)

        return keys

    def validate_key_format(self, key: str) -> bool:
        """Validate license key format"""
        key = key.strip().upper()
        parts = key.split('-')

        if len(parts) != 5:
            return False

        if parts[0] not in self.VALID_PREFIXES:
            return False

        for part in parts[1:]:
            if len(part) != 4:
                return False
            if not all(c in string.ascii_uppercase + string.digits for c in part):
                return False

        return True

    def validate_key(self, key: str) -> bool:
        """Check if license key is valid"""
        key = key.strip().upper()

        if not self.validate_key_format(key):
            return False

        return key in self._valid_keys

    def activate(self, key: str) -> tuple[bool, str]:
        """
        Activate a license key

        Returns (success, message)
        """
        key = key.strip().upper()

        if not self.validate_key_format(key):
            return False, "Invalid license key format"

        if not self.validate_key(key):
            return False, "License key not found or already used"

        # Determine license type from prefix
        prefix = key.split('-')[0]
        license_type = {
            "NEOS": "pro",
            "NEOFOX": "team",
            "TEAM": "enterprise"
        }.get(prefix, "pro")

        # Create license info
        self._license = LicenseInfo(
            license_key=key,
            activation_date=datetime.now().isoformat(),
            machine_id=self._get_machine_id(),
            license_type=license_type,
            max_clips=500 if license_type == "pro" else 1000,
            features=['all']
        )

        # Save to file
        self._save_license()

        return True, f"License activated successfully! Type: {license_type.upper()}"

    def _save_license(self):
        """Save license to file"""
        if self._license is None:
            return

        path = self._get_license_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        data = asdict(self._license)
        # Encrypt/obfuscate in production
        encoded = json.dumps(data)

        with open(path, 'w') as f:
            f.write(encoded)

    def _load_license(self) -> bool:
        """Load license from file"""
        path = self._get_license_path()

        if not path.exists():
            return False

        try:
            with open(path, 'r') as f:
                data = json.loads(f.read())

            self._license = LicenseInfo(**data)

            # Verify machine ID
            if self._license.machine_id != self._get_machine_id():
                self._license = None
                return False

            return True

        except Exception as e:
            print(f"Error loading license: {e}")
            return False

    def is_licensed(self) -> bool:
        """Check if currently licensed"""
        if self._license is not None:
            return True

        return self._load_license()

    def get_license_info(self) -> Optional[LicenseInfo]:
        """Get current license info"""
        if self._license is None:
            self._load_license()
        return self._license

    def get_max_clips(self) -> int:
        """Get maximum allowed clips"""
        if not self.is_licensed():
            return 5  # Trial limit
        return self._license.max_clips if self._license else 5

    def deactivate(self):
        """Deactivate current license"""
        self._license = None
        path = self._get_license_path()
        if path.exists():
            path.unlink()

    def get_trial_remaining(self) -> int:
        """Get remaining trial clips (if in trial mode)"""
        if self.is_licensed():
            return -1  # Unlimited
        return 5  # Trial allows 5 clips

    def export_keys(self, filepath: str):
        """Export all valid keys to file (for admin)"""
        keys = sorted(list(self._valid_keys))
        with open(filepath, 'w') as f:
            for key in keys:
                f.write(key + '\n')


# Pre-generated 500 license keys (printed for reference)
def print_all_keys():
    """Print all 500 license keys"""
    lm = LicenseManager()
    keys = sorted(list(lm._valid_keys))
    print(f"=== NeoSync License Keys ({len(keys)} total) ===\n")
    for i, key in enumerate(keys, 1):
        print(f"{i:3d}. {key}")
    return keys


if __name__ == "__main__":
    print_all_keys()
