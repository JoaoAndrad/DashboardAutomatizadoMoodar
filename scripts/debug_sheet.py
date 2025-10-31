#!/usr/bin/env python3
"""Lightweight debug helper to decrypt local credential blobs and preview a Sheets tab.
Purpose: confirm service account access and optionally download files referenced in column C.
"""
from pathlib import Path
import json
import os
import sys
from typing import Dict

# Ensure repo root is on sys.path so we can import package modules when run from scripts/
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

MASTER_PASSWORD = "joaoandrade"  # per user request


def find_creds_dir() -> Path:
    # Allow explicit override for credential dir via env var (useful for local tests)
    env_override = os.environ.get('DV_CRED_DIR')
    if env_override:
        p = Path(env_override)
        if p.exists():
            return p

    # Prefer credentials stored in user's LocalStore (AppData) when available.
    try:
        from dv_admin_automator.activation.storage import LocalStore
        ls = LocalStore()
        if ls and ls.creds_dir and ls.creds_dir.exists():
            return ls.creds_dir
    except Exception:
        pass

    # Fallback to repository ./credenciais
    root = Path(__file__).resolve().parent.parent
    local = root / "credenciais"
    return local


def decrypt_all(creds_dir: Path, master_password: str) -> Dict[str, bytes]:
    results = {}
    from dv_admin_automator.activation.verify import verify_token
    if not creds_dir.exists():
        print(f"credentials dir not found: {creds_dir}")
        return results
    for p in sorted(creds_dir.iterdir()):
        if not p.is_file():
            continue
        if not p.name.endswith('.enc'):
            continue
        name = p.name
        token = p.read_text(encoding='utf-8')
        salt_path = creds_dir / (name + '.salt')
        if not salt_path.exists():
            print(f"missing salt for {name}, expected {salt_path}")
            continue
        salt_b64 = salt_path.read_text(encoding='utf-8')
        try:
            plaintext = verify_token(token, salt_b64, master_password)
            results[name] = plaintext
        except Exception as e:
            print(f"failed to decrypt {name}: {e}")
    return results


def pretty_print_decrypted(results: Dict[str, bytes]):
    """Parse decrypted byte blobs into JSON or raw text and return a dict.

    This function no longer prints raw private keys. It only returns parsed
    representations for later analysis.
    """
    parsed = {}
    for name, data in results.items():
        try:
            text = data.decode('utf-8')
        except Exception:
            parsed[name] = {'_raw_bytes_len': len(data)}
            continue
        # try JSON
        try:
            j = json.loads(text)
            parsed[name] = j
        except Exception:
            parsed[name] = text
    return parsed


def analyze_and_print(parsed: Dict[str, object]):
    # Minimal, safe summary: counts and a short identifier for service accounts.
    svc_count = oauth_count = cache_count = other_count = 0
    sa_summaries = []
    for name, obj in parsed.items():
        if isinstance(obj, dict):
            if obj.get('type') == 'service_account' or ('client_email' in obj and 'private_key' in obj):
                svc_count += 1
                sa_summaries.append({'file': name, 'client_email': obj.get('client_email'), 'project_id': obj.get('project_id')})
            elif 'installed' in obj and isinstance(obj.get('installed'), dict):
                oauth_count += 1
            elif 'companies' in name.lower() or 'companies_cache' in name.lower() or 'companies' in json.dumps(obj).lower():
                cache_count += 1
            else:
                other_count += 1
        else:
            other_count += 1

    print('\n=== Decrypted blobs summary ===')
    print(f'service_account: {svc_count}, oauth_client_installed: {oauth_count}, cache-like: {cache_count}, other: {other_count}')
    if sa_summaries:
        print('Service account(s) found:')
        for s in sa_summaries:
            print(' -', s.get('file'), '-', s.get('client_email') or '<no-email>', '/', s.get('project_id') or '<no-project>')


def find_service_account(parsed: Dict[str, object]):
    for name, obj in parsed.items():
        if isinstance(obj, dict):
            if obj.get('type') == 'service_account':
                return name, obj
            if 'client_email' in obj and 'private_key' in obj:
                return name, obj
    return None, None


def fetch_sheet_rows(service_account_info: dict, sheet_id: str, tab: str = 'Base'):
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except Exception as e:
        print('Google client libraries not installed:', e)
        return None
    creds = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'],
    )
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    # Only read columns A through D per user request (ignore E+). Keep header + up to row 157.
    rng = f"{tab}!A1:D157"  # header + up to row 157
    try:
        res = sheet.values().get(spreadsheetId=sheet_id, range=rng).execute()
        return res.get('values', [])
    except Exception as e:
        print('Sheets API error:', e)
        return None


def fetch_sheet_preview_by_id(service_account_info: dict, linked_sheet_id: str, tab: str = None, max_rows: int = 5):
    """Try to fetch a small preview from another sheet (linked in column C).
    Returns list of rows or None on error."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except Exception as e:
        print('Google client libraries not installed for linked preview:', e)
        return None
    try:
        creds = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'],
        )
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        rng = f"{tab}!A1:Z{max_rows}" if tab else f"A1:Z{max_rows}"
        res = sheet.values().get(spreadsheetId=linked_sheet_id, range=rng).execute()
        return res.get('values', [])
    except Exception as e:
        # return the exception message for diagnostics
        return {'error': str(e)}


def fetch_column_grid_data(service_account_info: dict, sheet_id: str, tab: str, start_row: int = 2, end_row: int = 11, col_letter: str = 'C'):
    """Fetch grid data for a specific column range (to inspect hyperlinks and notes).
    Returns list of cellData dicts or {'error': msg} on failure."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except Exception as e:
        print('Google client libraries not installed for grid data fetch:', e)
        return None
    try:
        creds = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'],
        )
        service = build('sheets', 'v4', credentials=creds)
        # build A1 range for the column
        rng = f"{tab}!{col_letter}{start_row}:{col_letter}{end_row}"
        req = service.spreadsheets().get(spreadsheetId=sheet_id, ranges=[rng], includeGridData=True)
        res = req.execute()
        sheets = res.get('sheets', [])
        if not sheets:
            return []
        data = sheets[0].get('data', [])
        if not data:
            return []
        row_data = data[0].get('rowData', [])
        return row_data
    except Exception as e:
        return {'error': str(e)}


def list_drive_folder(service_account_info: dict, folder_id: str, max_files: int = 10):
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except Exception as e:
        print('Google client libraries not installed for Drive check:', e)
        return None
    try:
        creds = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=['https://www.googleapis.com/auth/drive.metadata.readonly'],
        )
        drive = build('drive', 'v3', credentials=creds)
        q = f"'{folder_id}' in parents and trashed = false"
        res = drive.files().list(q=q, pageSize=max_files, fields='files(id,name,mimeType)').execute()
        return res.get('files', [])
    except Exception as e:
        return {'error': str(e)}


def download_sheet_export(service_account_info: dict, file_id: str, dest_dir: str):
    """Attempt to download/export a Google Sheet (or report error).

    - If the file is a Google Sheets doc, use drive.files().export to get an XLSX binary.
    - Save to dest_dir with a safe filename and return the local path on success.
    - Return dict with {'error': msg} on failure.
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except Exception as e:
        return {'error': f'google client libs missing: {e}'}
    try:
        creds = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=['https://www.googleapis.com/auth/drive.readonly'],
        )
        drive = build('drive', 'v3', credentials=creds)
        # Try to get basic metadata first to form a filename and check mimeType
        meta = drive.files().get(fileId=file_id, fields='id,name,mimeType').execute()
        name = meta.get('name') or file_id
        mime = meta.get('mimeType') or ''
        # sanitize name for filesystem
        safe_name = ''.join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        out_dir = Path(dest_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        # If it's a native Google Sheets file (Docs Editors MIME), export to XLSX
        # NOTE: files().export only works for Google Docs editors files (mime like
        # 'application/vnd.google-apps.spreadsheet'). Do NOT match generic 'spreadsheet'
        # substrings (they may match office/xlsx types). Use the Google-specific MIME.
        if 'vnd.google-apps.spreadsheet' in mime:
            # Export Google Sheets to an XLSX file using the sheet's name only (no ID suffix)
            out_path = out_dir / f"{safe_name}.xlsx"
            try:
                req = drive.files().export(fileId=file_id, mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                data = req.execute()
                with open(out_path, 'wb') as fh:
                    fh.write(data)
                return {'path': str(out_path)}
            except Exception as e:
                return {'error': str(e)}
        else:
            # For non-Google files, attempt to download binary using get_media
            try:
                req = drive.files().get_media(fileId=file_id)
                from googleapiclient.http import MediaIoBaseDownload
                import io
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, req)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                # write to file using original (sanitized) name only (no ID suffix)
                if '.' in name:
                    ext = name.split('.')[-1]
                    out_path = out_dir / f"{safe_name}.{ext}"
                else:
                    out_path = out_dir / f"{safe_name}"
                with open(out_path, 'wb') as wf:
                    wf.write(fh.getvalue())
                return {'path': str(out_path)}
            except Exception as e:
                return {'error': str(e)}
    except Exception as e:
        return {'error': str(e)}


def search_files_in_folder_by_name(service_account_info: dict, folder_id: str, basename: str, max_files: int = 10):
    """Search for files in a Drive folder matching basename (exact or containing).

    Returns list of files (dicts with id,name,mimeType) or {'error': msg}.
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except Exception as e:
        return {'error': f'google client libs missing: {e}'}
    try:
        creds = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=['https://www.googleapis.com/auth/drive.readonly'],
        )
        drive = build('drive', 'v3', credentials=creds)
        # escape single quotes in basename
        safe_basename = str(basename).replace("'", "\\'")
        # build query: files in folder AND (name = 'basename.csv' OR name = 'basename.xlsx' OR name contains 'basename')
        q_parts = []
        q_parts.append(f"name = '{safe_basename}.csv'")
        q_parts.append(f"name = '{safe_basename}.xlsx'")
        q_parts.append(f"name contains '{safe_basename}'")
        q = f"'{folder_id}' in parents and trashed = false and ({' or '.join(q_parts)})"
        res = drive.files().list(q=q, pageSize=max_files, fields='files(id,name,mimeType)').execute()
        return res.get('files', [])
    except Exception as e:
        return {'error': str(e)}


def search_and_download_by_basename(service_account_info: dict, folder_id: str, basename: str, dest_dir: str):
    """Search files by basename in folder and try to download each candidate.

    Returns list of result dicts: {'id','name','mimeType','download': {'path'|'error'}}
    """
    files = search_files_in_folder_by_name(service_account_info, folder_id, basename, max_files=20)
    if files is None:
        return {'error': 'search returned None'}
    if isinstance(files, dict) and files.get('error'):
        return {'error': files.get('error')}
    # Apply strict case-sensitive matching rules per user request:
    # - If the provided basename includes an extension (contains a dot), match the full
    #   filename exactly (case-sensitive). E.g. "mv.xlsx" will match only files named
    #   exactly "mv.xlsx" (same case).
    # - If the provided basename has no extension, match the file's name without extension
    #   exactly (case-sensitive). E.g. "mv" will match "mv" but not "MV" nor "mv.xlsx"
    #   (unless the file's name without extension is exactly "mv").
    # This enforces strict case sensitivity and avoids downloading similarly-named files
    # that differ only in case.
    wanted = str(basename)
    exact_matches = []
    for f in files:
        fname = f.get('name') or ''
        # if user provided an extension, compare full filename exact (case-sensitive)
        if '.' in wanted:
            if fname == wanted:
                exact_matches.append(f)
        else:
            # compare name without extension exactly (case-sensitive)
            if '.' in fname:
                name_no_ext = fname.rsplit('.', 1)[0]
            else:
                name_no_ext = fname
            if name_no_ext == wanted:
                exact_matches.append(f)

    # If no exact case-sensitive matches found, try fallback: exact filename with .xlsx
    if not exact_matches:
        fallback_name = f"{wanted}.xlsx"
        fallback_matches = [f for f in files if (f.get('name') or '') == fallback_name]
        if fallback_matches:
            exact_matches = fallback_matches
        else:
            return []

    results = []
    for f in exact_matches:
        fid = f.get('id')
        name = f.get('name')
        mime = f.get('mimeType')
        dl = download_sheet_export(service_account_info, fid, dest_dir=dest_dir)
        results.append({'id': fid, 'name': name, 'mimeType': mime, 'download': dl})
    return results


def evaluate_file_access(service_account_info: dict, file_id: str, file_name: str, mime: str, drive_folder: str, dest_dir: str):
    """Evaluate access for a Drive file:
    - Try to get metadata including capabilities (readable metadata)
    - If it's a Google Sheet, try to preview a few rows (read test)
    - Determine can_edit from capabilities
    - If metadata/preview fails, attempt download
    Returns dict with keys: id,name,mime,readable(bool),can_edit(bool),download(path|error|null),error
    """
    out = {'id': file_id, 'name': file_name, 'mimeType': mime, 'readable': False, 'can_edit': False, 'download': None, 'error': None}
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except Exception as e:
        out['error'] = f'google client libs missing: {e}'
        return out
    try:
        creds = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/spreadsheets.readonly'],
        )
        drive = build('drive', 'v3', credentials=creds)
        # Attempt to read file metadata (includes capabilities)
        meta = drive.files().get(fileId=file_id, fields='id,name,mimeType,capabilities').execute()
        out['readable'] = True
        caps = meta.get('capabilities') or {}
        out['can_edit'] = bool(caps.get('canEdit') or caps.get('canEdit'))
        # If it's a Google Sheet, attempt a small preview to ensure Sheets API access
        if 'vnd.google-apps.spreadsheet' in mime:
            try:
                preview = fetch_sheet_preview_by_id(service_account_info, file_id, max_rows=2)
                if isinstance(preview, dict) and preview.get('error'):
                    # preview failed; mark readable False and attempt download
                    out['readable'] = False
                    dl = download_sheet_export(service_account_info, file_id, dest_dir=dest_dir)
                    out['download'] = dl
                    if isinstance(dl, dict) and dl.get('error'):
                        out['error'] = dl.get('error')
                else:
                    # preview succeeded
                    out['readable'] = True
            except Exception as e:
                # preview attempt threw
                out['readable'] = False
                dl = download_sheet_export(service_account_info, file_id, dest_dir=dest_dir)
                out['download'] = dl
                if isinstance(dl, dict) and dl.get('error'):
                    out['error'] = dl.get('error')
    except Exception as e:
        # metadata access failed -> try to download/export as fallback
        out['readable'] = False
        try:
            dl = download_sheet_export(service_account_info, file_id, dest_dir=dest_dir)
            out['download'] = dl
            if isinstance(dl, dict) and dl.get('error'):
                out['error'] = dl.get('error')
        except Exception as ee:
            out['error'] = str(ee)
    return out


def search_and_process_by_basename(service_account_info: dict, folder_id: str, basename: str, dest_dir: str):
    """Search files by basename and evaluate access for exact matches (with .xlsx fallback).
    Returns dict with keys: 'readable', 'editable', 'downloaded', 'no_access' each a list of per-file dicts.
    """
    files = search_files_in_folder_by_name(service_account_info, folder_id, basename, max_files=50)
    if files is None:
        return {'error': 'search returned None'}
    if isinstance(files, dict) and files.get('error'):
        return {'error': files.get('error')}

    wanted = str(basename)
    exact_matches = []
    for f in files:
        fname = f.get('name') or ''
        if '.' in wanted:
            if fname == wanted:
                exact_matches.append(f)
        else:
            if '.' in fname:
                name_no_ext = fname.rsplit('.', 1)[0]
            else:
                name_no_ext = fname
            if name_no_ext == wanted:
                exact_matches.append(f)

    if not exact_matches:
        # fallback to wanted.xlsx
        fallback_name = f"{wanted}.xlsx"
        fallback_matches = [f for f in files if (f.get('name') or '') == fallback_name]
        if fallback_matches:
            exact_matches = fallback_matches
        else:
            return {'readable': [], 'editable': [], 'downloaded': [], 'no_access': []}

    readable = []
    editable = []
    downloaded = []
    no_access = []

    for f in exact_matches:
        fid = f.get('id')
        name = f.get('name')
        mime = f.get('mimeType')
        info = evaluate_file_access(service_account_info, fid, name, mime, folder_id, dest_dir)
        if info.get('readable') and info.get('can_edit'):
            editable.append(info)
        elif info.get('readable') and not info.get('can_edit'):
            readable.append(info)
        elif info.get('download'):
            downloaded.append(info)
        else:
            no_access.append(info)

    return {'readable': readable, 'editable': editable, 'downloaded': downloaded, 'no_access': no_access}


def main():
    # Prefer the explicit local cred path if it exists (user provided)
    preferred = Path(r"C:\Users\andrade\AppData\Local\dv_admin_automator\dv_admin_automator\credenciais")
    creds_dir = preferred if preferred.exists() else find_creds_dir()
    print('Using credentials dir:', creds_dir)
    results = decrypt_all(creds_dir, MASTER_PASSWORD)
    if not results:
        print('No decrypted credentials found.')
        return 1
    parsed = pretty_print_decrypted(results)

    # Analyze and print a safe summary of decrypted blobs.
    analyze_and_print(parsed)

    # Attempt to find a service account and fetch the first rows from the
    # sheet tab 'Base'. We will NOT print any private key or client secret.
    name, sa = find_service_account(parsed)
    if sa is None:
        print('\nNo service account JSON found among decrypted blobs. Skipping fetch.')
        return 0
    print(f"\nUsing service account from: {name} (not printed)")
    # sheet and drive folder ids (allow env override)
    sheet_id = os.environ.get('ACOLH_SHEET_ID') or '1VTf5wWDp7_Tt9DRdsLhAjqgp4EAEnMdzwMCbaBqw3dM'
    drive_folder = os.environ.get('ACOLH_DRIVE_FOLDER') or '11TK5MG_piXzNMl_hj-B3hw4z4Y2bFtJG'
    print('Using spreadsheet id:', sheet_id)
    print('Using drive folder id:', drive_folder)

    tab_name = os.environ.get('ACOLH_SHEET_TAB') or 'Página1'
    print('Using sheet tab:', tab_name)
    rows = fetch_sheet_rows(sa, sheet_id, tab=tab_name)
    if rows is None:
        print('Failed to fetch sheet rows. See message above for details.')
        return 1

    print('\nSheet preview (columns A–D; header + up to 30 rows):')
    # print header and up to 10 rows, truncate long cell values for safety
    def safe_cell(c):
        s = '' if c is None else str(c)
        return s if len(s) <= 300 else s[:297] + '...'

    header = rows[0] if len(rows) > 0 else []
    print('Header:', [safe_cell(h) for h in header])
    # Print data rows (rows list already contains header at index 0) up to configured limit
    for idx, r in enumerate(rows[1:157], start=2):
        # Ensure we only display columns A..D even if the API returned fewer/extra columns
        row_cells = [r[i] if i < len(r) else '' for i in range(4)]
        print(f'Row {idx}:', [safe_cell(c) for c in row_cells])

    # Inspect column C (index 2) for linked sheets
    import re
    sheet_url_re = re.compile(r'(?:/spreadsheets/d/|docs.google.com/spreadsheets/d/)([a-zA-Z0-9-_]+)')
    print('\nInspecting column C (links) for rows 2..157 — only cells within A..D were read; E+ ignored:')
    for i, r in enumerate(rows[1:157], start=2):
        # r contains only A..D range; column C is index 2
        raw_c = r[2] if len(r) > 2 else ''
        if not raw_c:
            print(f'Row {i}: column C empty')
            continue
        print(f'Row {i}: C value: {safe_cell(raw_c)}')
        m = sheet_url_re.search(raw_c)
        if m:
            linked_id = m.group(1)
            print(f'  Detected Google Sheet id: {linked_id} — attempting preview')
            preview = fetch_sheet_preview_by_id(sa, linked_id, max_rows=3)
            if preview is None:
                print('   -> could not preview (missing libs?)')
            elif isinstance(preview, dict) and preview.get('error'):
                print('   -> preview error:', preview.get('error'))
            else:
                print('   -> preview (first rows):')
                for pr in preview[:3]:
                    print('      ', [safe_cell(x) for x in pr])
            # Try to download/export the spreadsheet (will fail if service account lacks permission)
            print('   -> attempting to download/export linked spreadsheet (dry attempt)...')
            dl = download_sheet_export(sa, linked_id, dest_dir=str(_repo_root / 'tmp_downloads'))
            if isinstance(dl, dict) and dl.get('error'):
                print('      download error:', dl.get('error'))
            else:
                print('      downloaded to:', dl.get('path'))
        else:
            # try to find a file id pattern (drive links)
            drive_id_re = re.compile(r'd/([a-zA-Z0-9-_]{10,})')
            dm = drive_id_re.search(raw_c)
            if dm:
                fid = dm.group(1)
                print(f'  Detected Drive file id: {fid} — attempting Sheets preview by id')
                preview = fetch_sheet_preview_by_id(sa, fid, max_rows=3)
                if preview is None:
                    print('   -> could not preview (missing libs?)')
                elif isinstance(preview, dict) and preview.get('error'):
                    print('   -> preview error:', preview.get('error'))
                else:
                    print('   -> preview (first rows):')
                    for pr in preview[:3]:
                        print('      ', [safe_cell(x) for x in pr])
                # Attempt to download/export (drive file) as well
                print('   -> attempting to download/export linked Drive file (dry attempt)...')
                dl = download_sheet_export(sa, fid, dest_dir=str(_repo_root / 'tmp_downloads'))
                if isinstance(dl, dict) and dl.get('error'):
                    print('      download error:', dl.get('error'))
                else:
                    print('      downloaded to:', dl.get('path'))
            else:
                # Not a link — try to find files in the specified Drive folder by basename
                base = str(raw_c).strip()
                if base:
                    print(f'  Column C contains text "{base}" — searching folder for matching .csv/.xlsx files')
                    proc = search_and_process_by_basename(sa, drive_folder, base, dest_dir=str(_repo_root / 'tmp_downloads'))
                    if isinstance(proc, dict) and proc.get('error'):
                        print('    search error:', proc.get('error'))
                    else:
                        # report editable
                        for p in proc.get('editable', []):
                            print(f'    readable+editable: {p.get("name")} ({p.get("id")})')
                        for p in proc.get('readable', []):
                            print(f'    readable (no edit): {p.get("name")} ({p.get("id")})')
                        for p in proc.get('downloaded', []):
                            dl = p.get('download')
                            if isinstance(dl, dict) and dl.get('path'):
                                print(f'    downloaded to: {dl.get("path")}')
                            else:
                                print(f'    attempted download but error: {dl.get("error") if isinstance(dl, dict) else dl}')
                        for p in proc.get('no_access', []):
                            print(f'    no access: {p.get("name")} ({p.get("id")}) error: {p.get("error") or "unknown"}')
                else:
                    print('  Not recognized as Google Sheet / Drive link and no basename to search; skipping')

    # (grid-data inspection removed to reduce verbosity at user's request)

    # Check Drive folder listing
    print('\nChecking Drive folder contents:')
    folder_list = list_drive_folder(sa, drive_folder, max_files=10)
    if folder_list is None:
        print('Drive libraries not available (google libs missing) or call failed')
    elif isinstance(folder_list, dict) and folder_list.get('error'):
        print('Drive listing error:', folder_list.get('error'))
    else:
        print('Drive files (first results):')
        for f in folder_list:
            print('  ', f.get('id'), '-', f.get('name'), '(', f.get('mimeType'), ')')

    return 0


if __name__ == '__main__':
    sys.exit(main())
