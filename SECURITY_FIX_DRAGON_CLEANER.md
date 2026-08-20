# Security Fix: Dragon Cleaner Arbitrary File Deletion Vulnerability

## Summary
This patch mitigates arbitrary host file and directory deletion through the `/api/delete` endpoint by implementing session-based authorization, path canonicalization, and containment validation.

## Vulnerability Details

### Original Issue
The `/api/delete` endpoint in `dragon_cleaner_server.py` was vulnerable to arbitrary file deletion attacks due to:

1. **No Authentication/Authorization**: Any client that could reach localhost:8917 could call the endpoint
2. **No Session Binding**: The endpoint accepted arbitrary paths without verifying they came from a scan session
3. **Path Traversal Vulnerability**: The `is_protected()` function only checked raw string prefixes without canonicalizing paths, allowing bypasses via:
   - Symbolic links
   - Relative paths (../)
   - Path normalization tricks
4. **No Containment Validation**: No verification that deletion paths were within the scanned directory

### Attack Scenario
An attacker-controlled web page or malicious client that could reach the localhost API could:
1. Submit arbitrary paths to `POST /api/delete` with `confirm: true`
2. Bypass the protection check using non-canonical paths (e.g., symlinks, relative paths)
3. Delete any files or directories the process could access

## Security Fixes Implemented

### 1. Path Canonicalization in `is_protected()` (Lines 75-89)

**Before:**
```python
def is_protected(path: str) -> bool:
    p = path.lower().replace('\\', '/')
    for proto in SYSTEM_PROTECTED:
        if p.startswith(proto.lower().replace('\\', '/')):
            return True
    return False
```

**After:**
```python
def is_protected(path: str) -> bool:
    """Check if a path is system-protected. Uses canonicalized path to prevent bypasses."""
    try:
        # Canonicalize the path to resolve symlinks and relative paths
        canonical = os.path.realpath(path)
        p = canonical.lower().replace('\\', '/')
    except (OSError, ValueError):
        # If we can't resolve the path, treat it as protected (fail-safe)
        return True
    
    for proto in SYSTEM_PROTECTED:
        proto_canonical = proto.lower().replace('\\', '/')
        if p.startswith(proto_canonical):
            return True
    return False
```

**Changes:**
- Uses `os.path.realpath()` to resolve symlinks and relative paths before checking protection
- Implements fail-safe behavior: if path cannot be resolved, treat it as protected
- Prevents bypass via path traversal tricks

### 2. Session-Based Authorization in `/api/delete` (Lines 455-558)

**Before:**
```python
@app.route('/api/delete', methods=['POST'])
def delete_paths():
    """
    ALWAYS requires explicit confirm=true. Never deletes speculatively.
    Request: {"paths": [...], "confirm": true}
    """
    data = request.get_json(force=True)
    paths = data.get('paths', [])
    if not data.get('confirm') is True:
        return jsonify({'error': 'Confirmation required (confirm: true)'}), 400
    if not isinstance(paths, list) or not paths:
        return jsonify({'error': 'No paths'}), 400

    deleted, failed, freed = [], [], 0
    for p in paths:
        if is_protected(p):
            failed.append({'path': p, 'error': 'protected'})
            continue
        if not os.path.exists(p):
            failed.append({'path': p, 'error': 'not found'})
            continue
        try:
            if os.path.isdir(p) and not os.path.islink(p):
                size = _dir_size(p)
                shutil.rmtree(p)
                freed += size
            else:
                size = os.path.getsize(p)
                os.remove(p)
                freed += size
            deleted.append(p)
        except Exception as e:
            failed.append({'path': p, 'error': str(e)})
```

**After:**
```python
@app.route('/api/delete', methods=['POST'])
def delete_paths():
    """
    Delete paths that were discovered in a specific scan session.
    Requires explicit confirm=true and a valid scan_id.
    Request: {"scan_id": "...", "paths": [...], "confirm": true}
    
    Security: Only allows deletion of paths that:
    1. Were discovered in the specified scan session
    2. Are within the scan root directory (after canonicalization)
    3. Are not system-protected (checked on canonical path)
    """
    data = request.get_json(force=True)
    scan_id = data.get('scan_id', '').strip()
    paths = data.get('paths', [])
    
    if not data.get('confirm') is True:
        return jsonify({'error': 'Confirmation required (confirm: true)'}), 400
    if not isinstance(paths, list) or not paths:
        return jsonify({'error': 'No paths'}), 400
    if not scan_id:
        return jsonify({'error': 'scan_id required'}), 400

    # Verify scan session exists and is complete
    with SCAN_LOCK:
        scan = SCANS.get(scan_id)
        if not scan:
            return jsonify({'error': 'Unknown scan_id'}), 404
        if scan.get('state') != 'complete':
            return jsonify({'error': f"Scan not complete (state={scan.get('state')})"}), 409
        
        scan_results = scan.get('results')
        if not scan_results:
            return jsonify({'error': 'No scan results available'}), 409
        
        scan_root = scan_results.get('scan_root')
        if not scan_root:
            return jsonify({'error': 'Scan root not found'}), 500

    # Canonicalize scan root once
    try:
        canonical_scan_root = os.path.realpath(scan_root)
    except (OSError, ValueError):
        return jsonify({'error': 'Cannot resolve scan root'}), 500

    # Build a set of all paths discovered in this scan for validation
    discovered_paths = set()
    for junk in scan_results.get('junk_files', []):
        discovered_paths.add(junk['path'])
    for large in scan_results.get('large_files', []):
        discovered_paths.add(large['path'])
    for dup_group in scan_results.get('duplicates', {}).values():
        for dup in dup_group:
            discovered_paths.add(dup['path'])

    deleted, failed, freed = [], [], 0
    for p in paths:
        # Validate path was discovered in this scan
        if p not in discovered_paths:
            failed.append({'path': p, 'error': 'path not from this scan session'})
            continue
        
        # Canonicalize the path to prevent traversal attacks
        try:
            canonical_path = os.path.realpath(p)
        except (OSError, ValueError):
            failed.append({'path': p, 'error': 'cannot resolve path'})
            continue
        
        # Verify path is within scan root (containment check)
        if not canonical_path.startswith(canonical_scan_root + os.sep) and canonical_path != canonical_scan_root:
            failed.append({'path': p, 'error': 'path outside scan root'})
            continue
        
        # Check system protection on canonical path
        if is_protected(canonical_path):
            failed.append({'path': p, 'error': 'protected'})
            continue
        
        # Verify path still exists
        if not os.path.exists(canonical_path):
            failed.append({'path': p, 'error': 'not found'})
            continue
        
        # Perform deletion
        try:
            if os.path.isdir(canonical_path) and not os.path.islink(canonical_path):
                size = _dir_size(canonical_path)
                shutil.rmtree(canonical_path)
                freed += size
            else:
                size = os.path.getsize(canonical_path)
                os.remove(canonical_path)
                freed += size
            deleted.append(p)
        except Exception as e:
            failed.append({'path': p, 'error': str(e)})
```

**Changes:**
- **Requires `scan_id`**: Endpoint now requires a valid scan session ID
- **Session Validation**: Verifies the scan session exists and is complete
- **Path Whitelist**: Only allows deletion of paths that were discovered in the scan
- **Containment Check**: Ensures all paths are within the scan root directory
- **Canonicalization**: Resolves all paths before validation to prevent traversal attacks
- **Defense in Depth**: Multiple layers of validation before any deletion occurs

### 3. Client-Side Update in `dragon-cleaner-app.html` (Lines 830-844)

**Before:**
```javascript
$('confirmYes').addEventListener('click', async () => {
  const paths = Object.keys(selection);
  $('confirmModal').classList.remove('active');
  try {
    const r = await fetch(`${API}/api/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths, confirm: true }),
    });
```

**After:**
```javascript
$('confirmYes').addEventListener('click', async () => {
  const paths = Object.keys(selection);
  $('confirmModal').classList.remove('active');
  if (!currentScanId) {
    alertFailure('No active scan session. Please run a scan first.');
    return;
  }
  try {
    const r = await fetch(`${API}/api/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scan_id: currentScanId, paths, confirm: true }),
    });
```

**Changes:**
- Validates that a scan session exists before attempting deletion
- Passes `scan_id` in the delete request
- Provides user-friendly error message if no scan session is active

## Security Properties

### Defense in Depth
The fix implements multiple layers of security:

1. **Session Binding**: Paths must come from a valid, completed scan session
2. **Path Whitelist**: Only paths discovered in the scan can be deleted
3. **Containment**: Paths must be within the scan root directory
4. **Canonicalization**: All paths are resolved before validation
5. **Protection Check**: System-protected paths are rejected
6. **Fail-Safe**: Errors in path resolution result in rejection

### Attack Mitigation

#### Path Traversal
- **Before**: `../../etc/passwd` could bypass protection checks
- **After**: Path is canonicalized to `/etc/passwd`, which is in SYSTEM_PROTECTED

#### Symlink Bypass
- **Before**: Symlink to `/etc/passwd` could bypass protection checks
- **After**: `os.path.realpath()` resolves symlinks before validation

#### Arbitrary Path Injection
- **Before**: Any path could be submitted for deletion
- **After**: Only paths from the scan session's discovered files can be deleted

#### Directory Escape
- **Before**: No verification that paths are within scan root
- **After**: Containment check ensures paths are within canonical scan root

## Testing Recommendations

### Positive Tests (Should Succeed)
1. Run a scan on a user directory
2. Select files from the scan results
3. Delete selected files
4. Verify files are deleted and response is successful

### Negative Tests (Should Fail)
1. **No Scan Session**: Attempt to delete without running a scan first
   - Expected: Error "scan_id required"

2. **Invalid Scan ID**: Attempt to delete with a non-existent scan_id
   - Expected: Error "Unknown scan_id"

3. **Path Not in Scan**: Attempt to delete a path not discovered in the scan
   - Expected: Error "path not from this scan session"

4. **Path Outside Scan Root**: Attempt to delete a path outside the scan directory
   - Expected: Error "path outside scan root"

5. **System Protected Path**: Attempt to delete a system-protected path
   - Expected: Error "protected"

6. **Path Traversal**: Attempt to delete using `../../etc/passwd`
   - Expected: Error "path not from this scan session" or "path outside scan root"

7. **Symlink Bypass**: Create symlink to protected file, attempt to delete
   - Expected: Error "protected" (after symlink resolution)

## Backward Compatibility

### Breaking Changes
- **API Change**: `/api/delete` now requires `scan_id` parameter
- **Client Update Required**: Clients must be updated to pass `scan_id`

### Migration Path
1. Update server code (dragon_cleaner_server.py)
2. Update client code (dragon-cleaner-app.html)
3. Both updates must be deployed together for functionality to work

## Additional Recommendations

### Future Enhancements
1. **Authentication**: Add API key or session token authentication
2. **Rate Limiting**: Implement rate limiting on delete endpoint
3. **Audit Logging**: Log all deletion attempts with timestamps and results
4. **CSRF Protection**: Add CSRF tokens for web-based clients
5. **Scan Expiry**: Implement time-based expiry for scan sessions
6. **User Confirmation**: Require additional confirmation for large deletions

### Deployment Notes
- The server binds to localhost (127.0.0.1) by default, limiting exposure
- CORS is enabled, allowing cross-origin requests from web clients
- Consider disabling CORS or restricting origins in production environments
- Consider adding authentication if the service will be exposed beyond localhost

## Files Modified

1. **dragon_cleaner_server.py**
   - Updated `is_protected()` function (lines 75-89)
   - Updated `/api/delete` endpoint (lines 455-558)

2. **dragon-cleaner-app.html**
   - Updated delete confirmation handler (lines 830-844)

## Conclusion

This patch successfully mitigates the arbitrary file deletion vulnerability by:
- Binding deletions to scan sessions
- Implementing path canonicalization to prevent traversal attacks
- Enforcing containment within scan root directories
- Maintaining defense-in-depth with multiple validation layers

The fix maintains the intended functionality while significantly improving security posture.
