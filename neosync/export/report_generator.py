"""
Report Generator
================

Generate detailed sync reports in various formats:
- CSV (spreadsheet)
- PDF (printable report)
- HTML (web viewable)
- JSON (machine readable)
"""

import csv
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import html

from ..core.sync_engine import ClipInfo, SyncProject, SyncStatus, SyncQuality


def seconds_to_timecode(seconds: float, fps: float = 24.0) -> str:
    """Convert seconds to timecode string"""
    negative = seconds < 0
    seconds = abs(seconds)
    frames = int(round(seconds * fps))
    fps_int = int(round(fps))
    f = frames % fps_int
    total_seconds = frames // fps_int
    s = total_seconds % 60
    total_minutes = total_seconds // 60
    m = total_minutes % 60
    h = total_minutes // 60
    sign = "-" if negative else ""
    return f"{sign}{h:02d}:{m:02d}:{s:02d}:{f:02d}"


class ReportGenerator:
    """
    Generate comprehensive sync reports
    """

    def __init__(self, project: SyncProject):
        self.project = project
        self.clips = project.clips

    def export_csv(self, output_path: str) -> str:
        """Export detailed CSV report"""
        output_path = str(Path(output_path))
        if not output_path.endswith('.csv'):
            output_path += '.csv'

        fieldnames = [
            'File Name',
            'File Path',
            'Duration',
            'Duration (TC)',
            'Sync Status',
            'Sync Quality',
            'Confidence',
            'Offset (seconds)',
            'Offset (TC)',
            'Sync Method',
            'Drift Rate',
            'Camera',
            'Has Audio',
            'Resolution',
            'FPS',
            'Codec',
            'Creation Time',
            'Notes'
        ]

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for clip in self.clips:
                fps = clip.metadata.fps if clip.metadata else 24.0

                row = {
                    'File Name': clip.file_name,
                    'File Path': clip.file_path,
                    'Duration': f"{clip.duration:.2f}s",
                    'Duration (TC)': seconds_to_timecode(clip.duration, fps),
                    'Sync Status': clip.sync_status.name,
                    'Sync Quality': clip.sync_quality.name,
                    'Confidence': f"{clip.sync_confidence:.1%}",
                    'Offset (seconds)': f"{clip.sync_offset_seconds:.4f}",
                    'Offset (TC)': seconds_to_timecode(clip.sync_offset_seconds, fps),
                    'Sync Method': clip.sync_method.value if clip.sync_method else 'N/A',
                    'Drift Rate': f"{clip.drift_rate:.4f}" if clip.drift_rate else '0',
                    'Camera': clip.camera_id or 'Unknown',
                    'Has Audio': 'Yes' if clip.has_audio else 'No',
                    'Resolution': f"{clip.metadata.width}x{clip.metadata.height}" if clip.metadata else 'N/A',
                    'FPS': f"{fps:.2f}",
                    'Codec': clip.metadata.video_codec if clip.metadata else 'N/A',
                    'Creation Time': clip.metadata.creation_time.isoformat() if clip.metadata and clip.metadata.creation_time else 'N/A',
                    'Notes': clip.error_message or ''
                }
                writer.writerow(row)

        return output_path

    def export_json(self, output_path: str) -> str:
        """Export machine-readable JSON report"""
        output_path = str(Path(output_path))
        if not output_path.endswith('.json'):
            output_path += '.json'

        report = {
            'project': {
                'name': self.project.name,
                'created_at': datetime.fromtimestamp(self.project.created_at).isoformat(),
                'modified_at': datetime.fromtimestamp(self.project.modified_at).isoformat(),
                'total_clips': len(self.clips),
                'synced_clips': self.project.total_synced,
                'failed_clips': self.project.total_failed,
                'average_confidence': self.project.average_confidence,
                'settings': {
                    'sample_rate': self.project.sample_rate,
                    'max_offset_seconds': self.project.max_offset_seconds,
                    'drift_correction': self.project.drift_correction,
                    'noise_reduction': self.project.noise_reduction,
                    'use_gpu': self.project.use_gpu
                }
            },
            'clips': []
        }

        for clip in self.clips:
            clip_data = {
                'id': clip.id,
                'file_name': clip.file_name,
                'file_path': clip.file_path,
                'duration': clip.duration,
                'sync': {
                    'status': clip.sync_status.name,
                    'quality': clip.sync_quality.name,
                    'confidence': clip.sync_confidence,
                    'offset_seconds': clip.sync_offset_seconds,
                    'offset_frames': clip.sync_offset_frames,
                    'method': clip.sync_method.value if clip.sync_method else None,
                    'drift_rate': clip.drift_rate,
                    'is_reference': clip.is_reference
                },
                'metadata': None,
                'error': clip.error_message
            }

            if clip.metadata:
                clip_data['metadata'] = {
                    'has_audio': clip.has_audio,
                    'width': clip.metadata.width,
                    'height': clip.metadata.height,
                    'fps': clip.metadata.fps,
                    'sample_rate': clip.metadata.sample_rate,
                    'video_codec': clip.metadata.video_codec,
                    'audio_codec': clip.metadata.audio_codec,
                    'camera_make': clip.metadata.camera_make,
                    'camera_model': clip.metadata.camera_model,
                    'creation_time': clip.metadata.creation_time.isoformat() if clip.metadata.creation_time else None
                }

            report['clips'].append(clip_data)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)

        return output_path

    def export_html(self, output_path: str) -> str:
        """Export HTML report with visual summary"""
        output_path = str(Path(output_path))
        if not output_path.endswith('.html'):
            output_path += '.html'

        # Count by quality
        quality_counts = {q: 0 for q in SyncQuality}
        for clip in self.clips:
            quality_counts[clip.sync_quality] += 1

        # Generate HTML
        html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NeoSync Report - {html.escape(self.project.name)}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #0f0f0f;
            color: #e0e0e0;
            line-height: 1.6;
            padding: 40px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        h1 {{
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .subtitle {{
            color: #888;
            margin-bottom: 40px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .stat-card {{
            background: #1a1a1a;
            border-radius: 12px;
            padding: 24px;
            border: 1px solid #333;
        }}
        .stat-value {{
            font-size: 2.5rem;
            font-weight: 700;
            color: #fff;
        }}
        .stat-label {{
            color: #888;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .quality-bar {{
            display: flex;
            height: 8px;
            border-radius: 4px;
            overflow: hidden;
            margin: 20px 0;
        }}
        .quality-segment {{
            height: 100%;
        }}
        .quality-excellent {{ background: #22C55E; }}
        .quality-good {{ background: #84CC16; }}
        .quality-fair {{ background: #EAB308; }}
        .quality-poor {{ background: #F97316; }}
        .quality-failed {{ background: #EF4444; }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th, td {{
            text-align: left;
            padding: 12px 16px;
            border-bottom: 1px solid #333;
        }}
        th {{
            background: #1a1a1a;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.8rem;
            letter-spacing: 1px;
            color: #888;
        }}
        tr:hover {{
            background: #1a1a1a;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .badge-excellent {{ background: #22C55E20; color: #22C55E; }}
        .badge-good {{ background: #84CC1620; color: #84CC16; }}
        .badge-fair {{ background: #EAB30820; color: #EAB308; }}
        .badge-poor {{ background: #F9731620; color: #F97316; }}
        .badge-failed {{ background: #EF444420; color: #EF4444; }}
        .badge-reference {{ background: #3B82F620; color: #3B82F6; }}

        .confidence {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .confidence-bar {{
            width: 60px;
            height: 6px;
            background: #333;
            border-radius: 3px;
            overflow: hidden;
        }}
        .confidence-fill {{
            height: 100%;
            border-radius: 3px;
        }}

        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #333;
            color: #666;
            font-size: 0.9rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>NeoSync Report</h1>
        <p class="subtitle">{html.escape(self.project.name)} • Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{len(self.clips)}</div>
                <div class="stat-label">Total Clips</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{self.project.total_synced}</div>
                <div class="stat-label">Synced</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{self.project.total_failed}</div>
                <div class="stat-label">Failed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{self.project.average_confidence:.1%}</div>
                <div class="stat-label">Avg Confidence</div>
            </div>
        </div>

        <div class="quality-bar">
            {self._generate_quality_bar(quality_counts)}
        </div>

        <table>
            <thead>
                <tr>
                    <th>File</th>
                    <th>Duration</th>
                    <th>Camera</th>
                    <th>Status</th>
                    <th>Confidence</th>
                    <th>Offset</th>
                    <th>Method</th>
                </tr>
            </thead>
            <tbody>
                {self._generate_table_rows()}
            </tbody>
        </table>

        <div class="footer">
            <p>Generated by NeoSync v1.0.0 • © NeoFox</p>
        </div>
    </div>
</body>
</html>'''

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return output_path

    def _generate_quality_bar(self, quality_counts: Dict[SyncQuality, int]) -> str:
        """Generate quality bar segments"""
        total = sum(quality_counts.values())
        if total == 0:
            return ''

        segments = []
        quality_classes = {
            SyncQuality.EXCELLENT: 'quality-excellent',
            SyncQuality.GOOD: 'quality-good',
            SyncQuality.FAIR: 'quality-fair',
            SyncQuality.POOR: 'quality-poor',
            SyncQuality.FAILED: 'quality-failed',
        }

        for quality, count in quality_counts.items():
            if count > 0:
                percent = (count / total) * 100
                css_class = quality_classes.get(quality, 'quality-failed')
                segments.append(f'<div class="quality-segment {css_class}" style="width: {percent}%"></div>')

        return ''.join(segments)

    def _generate_table_rows(self) -> str:
        """Generate table rows for clips"""
        rows = []
        sorted_clips = sorted(self.clips, key=lambda c: c.sync_offset_seconds)

        badge_classes = {
            SyncQuality.EXCELLENT: 'badge-excellent',
            SyncQuality.GOOD: 'badge-good',
            SyncQuality.FAIR: 'badge-fair',
            SyncQuality.POOR: 'badge-poor',
            SyncQuality.FAILED: 'badge-failed',
        }

        confidence_colors = {
            SyncQuality.EXCELLENT: '#22C55E',
            SyncQuality.GOOD: '#84CC16',
            SyncQuality.FAIR: '#EAB308',
            SyncQuality.POOR: '#F97316',
            SyncQuality.FAILED: '#EF4444',
        }

        for clip in sorted_clips:
            fps = clip.metadata.fps if clip.metadata else 24.0
            duration_tc = seconds_to_timecode(clip.duration, fps)
            offset_tc = seconds_to_timecode(clip.sync_offset_seconds, fps)

            badge_class = 'badge-reference' if clip.is_reference else badge_classes.get(clip.sync_quality, 'badge-failed')
            status_text = 'REFERENCE' if clip.is_reference else clip.sync_quality.name

            conf_color = confidence_colors.get(clip.sync_quality, '#EF4444')
            conf_percent = clip.sync_confidence * 100

            method = clip.sync_method.value if clip.sync_method else 'N/A'

            rows.append(f'''
                <tr>
                    <td>{html.escape(clip.file_name)}</td>
                    <td>{duration_tc}</td>
                    <td>{html.escape(clip.camera_id or 'Unknown')}</td>
                    <td><span class="badge {badge_class}">{status_text}</span></td>
                    <td>
                        <div class="confidence">
                            <div class="confidence-bar">
                                <div class="confidence-fill" style="width: {conf_percent}%; background: {conf_color}"></div>
                            </div>
                            <span>{clip.sync_confidence:.0%}</span>
                        </div>
                    </td>
                    <td>{offset_tc}</td>
                    <td>{method}</td>
                </tr>
            ''')

        return ''.join(rows)

    def export_pdf(self, output_path: str) -> str:
        """
        Export PDF report

        Note: Requires reportlab or weasyprint.
        Falls back to HTML if not available.
        """
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.units import inch

            return self._export_pdf_reportlab(output_path)

        except ImportError:
            # Fall back to HTML
            print("reportlab not installed, generating HTML instead")
            html_path = output_path.replace('.pdf', '.html')
            return self.export_html(html_path)

    def _export_pdf_reportlab(self, output_path: str) -> str:
        """Export PDF using reportlab"""
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.units import inch

        output_path = str(Path(output_path))
        if not output_path.endswith('.pdf'):
            output_path += '.pdf'

        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Title
        title_style = styles['Heading1']
        elements.append(Paragraph(f"NeoSync Report: {self.project.name}", title_style))
        elements.append(Spacer(1, 12))

        # Summary
        summary_text = f"""
        Total Clips: {len(self.clips)} |
        Synced: {self.project.total_synced} |
        Failed: {self.project.total_failed} |
        Average Confidence: {self.project.average_confidence:.1%}
        """
        elements.append(Paragraph(summary_text, styles['Normal']))
        elements.append(Spacer(1, 24))

        # Table
        table_data = [['File', 'Duration', 'Status', 'Confidence', 'Offset']]

        for clip in sorted(self.clips, key=lambda c: c.sync_offset_seconds):
            fps = clip.metadata.fps if clip.metadata else 24.0
            table_data.append([
                clip.file_name[:30],
                f"{clip.duration:.1f}s",
                clip.sync_quality.name,
                f"{clip.sync_confidence:.0%}",
                f"{clip.sync_offset_seconds:.2f}s"
            ])

        table = Table(table_data, colWidths=[2.5*inch, 1*inch, 1*inch, 1*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        elements.append(table)
        elements.append(Spacer(1, 24))

        # Footer
        elements.append(Paragraph(
            f"Generated by NeoSync v1.0.0 • {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            styles['Normal']
        ))

        doc.build(elements)
        return output_path
