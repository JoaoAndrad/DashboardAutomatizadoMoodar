package main

import (
    "archive/zip"
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "flag"
    "fmt"
    "io"
    "io/ioutil"
    "net/http"
    "os"
    "os/exec"
    "path/filepath"
    "strings"
    "time"
)

type releaseAsset struct {
    Name               string `json:"name"`
    BrowserDownloadURL string `json:"browser_download_url"`
}

type githubRelease struct {
    TagName string         `json:"tag_name"`
    Assets  []releaseAsset `json:"assets"`
}

func httpGet(url string) ([]byte, error) {
    client := &http.Client{Timeout: 60 * time.Second}
    resp, err := client.Get(url)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    if resp.StatusCode < 200 || resp.StatusCode >= 300 {
        return nil, fmt.Errorf("http status %d for %s", resp.StatusCode, url)
    }
    return ioutil.ReadAll(resp.Body)
}

func downloadFile(dest, url string) error {
    client := &http.Client{Timeout: 0}
    resp, err := client.Get(url)
    if err != nil {
        return err
    }
    defer resp.Body.Close()

    f, err := os.Create(dest)
    if err != nil {
        return err
    }
    defer f.Close()
    _, err = io.Copy(f, resp.Body)
    return err
}

func findAsset(assets []releaseAsset, prefix string) *releaseAsset {
    for _, a := range assets {
        if strings.HasPrefix(a.Name, prefix) {
            return &a
        }
    }
    return nil
}

func verifySha256(filePath, expectedHex string) error {
    f, err := os.Open(filePath)
    if err != nil {
        return err
    }
    defer f.Close()
    h := sha256.New()
    if _, err := io.Copy(h, f); err != nil {
        return err
    }
    got := hex.EncodeToString(h.Sum(nil))
    if !strings.EqualFold(got, strings.TrimSpace(expectedHex)) {
        return fmt.Errorf("sha256 mismatch: got %s expected %s", got, expectedHex)
    }
    return nil
}

func unzip(src, dest string) error {
    r, err := zip.OpenReader(src)
    if err != nil {
        return err
    }
    defer r.Close()

    for _, f := range r.File {
        fp := filepath.Join(dest, f.Name)
        if f.FileInfo().IsDir() {
            if err := os.MkdirAll(fp, 0o755); err != nil {
                return err
            }
            continue
        }
        if err := os.MkdirAll(filepath.Dir(fp), 0o755); err != nil {
            return err
        }
        out, err := os.OpenFile(fp, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, f.Mode())
        if err != nil {
            return err
        }
        rc, err := f.Open()
        if err != nil {
            out.Close()
            return err
        }
        _, err = io.Copy(out, rc)
        out.Close()
        rc.Close()
        if err != nil {
            return err
        }
    }
    return nil
}

func pathExists(p string) bool {
    _, err := os.Stat(p)
    return err == nil
}

func isDir(p string) bool {
    fi, err := os.Stat(p)
    if err != nil {
        return false
    }
    return fi.IsDir()
}

// Heuristic: check whether a directory looks like the project by looking for
// known files or folders (requirements.txt, scripts/start_server.py, dv_admin_automator)
func hasProjectIndicators(p string) bool {
    if !pathExists(p) || !isDir(p) {
        return false
    }
    indicators := []string{
        "requirements.txt",
        "scripts/start_server.py",
        "dv_admin_automator",
    }
    for _, ind := range indicators {
        if pathExists(filepath.Join(p, ind)) {
            return true
        }
    }
    return false
}

func copyFile(src, dst string) error {
    in, err := os.Open(src)
    if err != nil {
        return err
    }
    defer in.Close()
    if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
        return err
    }
    out, err := os.Create(dst)
    if err != nil {
        return err
    }
    defer out.Close()
    if _, err := io.Copy(out, in); err != nil {
        return err
    }
    if fi, err := os.Stat(src); err == nil {
        _ = os.Chmod(dst, fi.Mode())
    }
    return nil
}

func copyDir(srcDir, dstDir string) error {
    entries, err := ioutil.ReadDir(srcDir)
    if err != nil {
        return err
    }
    for _, e := range entries {
        srcPath := filepath.Join(srcDir, e.Name())
        dstPath := filepath.Join(dstDir, e.Name())
        if e.IsDir() {
            if err := copyDir(srcPath, dstPath); err != nil {
                return err
            }
        } else {
            if err := copyFile(srcPath, dstPath); err != nil {
                return err
            }
        }
    }
    return nil
}

// moveContents moves the contents of srcDir into dstDir (creates dstDir if needed)
func moveContents(srcDir, dstDir string) error {
    if err := os.MkdirAll(dstDir, 0o755); err != nil {
        return err
    }
    entries, err := ioutil.ReadDir(srcDir)
    if err != nil {
        return err
    }
    for _, e := range entries {
        srcPath := filepath.Join(srcDir, e.Name())
        dstPath := filepath.Join(dstDir, e.Name())
        // try rename first
        if err := os.Rename(srcPath, dstPath); err == nil {
            continue
        }
        // fallback to copy
        if e.IsDir() {
            if err := copyDir(srcPath, dstPath); err != nil {
                return err
            }
        } else {
            if err := copyFile(srcPath, dstPath); err != nil {
                return err
            }
        }
    }
    return nil
}

// getUserDocumentsDir returns the user's Documents directory.
// On most systems this is $HOME/Documents. We keep it simple and fallback to the home dir.
func getUserDocumentsDir() string {
    if h, err := os.UserHomeDir(); err == nil {
        docs := filepath.Join(h, "Documents")
        if pathExists(docs) {
            return docs
        }
        // fallback to home
        return h
    }
    // as a last resort, use current directory
    return "."
}

// ensureResidentLauncher makes sure a copy of the current executable exists in
// Documents/Moodinho as "moodinho-launcher" (+ extension) and, if the running
// executable is not the resident one, starts the resident launcher with the
// same args and exits the current process after the resident finishes.
func ensureResidentLauncher() {
    exePath, err := os.Executable()
    if err != nil {
        // cannot determine executable; continue without resident delegation
        return
    }
    exePath, _ = filepath.Abs(exePath)

    docs := getUserDocumentsDir()
    moodinhoDir := filepath.Join(docs, "Moodinho")
    if err := os.MkdirAll(moodinhoDir, 0o755); err != nil {
        // if we can't create the dir, skip resident install
        return
    }

    ext := filepath.Ext(exePath)
    residentName := "moodinho-launcher" + ext
    residentPath := filepath.Join(moodinhoDir, residentName)

    // If current executable is already the resident, nothing to do
    curClean, _ := filepath.Abs(exePath)
    resClean, _ := filepath.Abs(residentPath)
    if strings.EqualFold(curClean, resClean) {
        return
    }

    // Copy the exe to resident location if missing or differs (we keep it simple and overwrite)
    if err := copyFile(exePath, residentPath); err != nil {
        // failed to copy: skip delegation
        return
    }
    // Ensure executable bit on non-Windows
    _ = os.Chmod(residentPath, 0o755)

    // Start resident launcher with the same args and proxy IO; wait for it to finish
    args := os.Args[1:]
    // Ensure the resident launcher will operate on Documents/Moodinho/project
    residentProject := filepath.Join(moodinhoDir, "project")
    // If user did not provide a --project flag, add it so the resident will
    // use the central Documents/Moodinho/project location by default.
    hasProject := false
    for _, a := range args {
        if a == "--project" || a == "-project" || strings.HasPrefix(a, "--project=") || strings.HasPrefix(a, "-project=") {
            hasProject = true
            break
        }
    }
    if !hasProject {
        args = append(args, "--project", residentProject)
    }

    // Create the resident project dir if missing (empty bootstrap)
    _ = os.MkdirAll(residentProject, 0o755)

    cmd := exec.Command(residentPath, args...)
    cmd.Stdout = os.Stdout
    cmd.Stderr = os.Stderr
    cmd.Stdin = os.Stdin
    if err := cmd.Run(); err != nil {
        // If resident failed, propagate error code
        fmt.Fprintf(os.Stderr, "resident launcher failed: %v\n", err)
        os.Exit(1)
    }
    // On success, exit current process. The resident launcher performed the work.
    os.Exit(0)
}

// findPython3Command probes common python commands and returns one that
// executes and reports major version 3. It checks (in order):
// - on Windows: "py -3", "python", "python3"
// - on other OS: "python3", "python"
// findPython3Command probes common python commands and returns a command slice
// suitable for exec.Command (program and args). Example returns: {"py","-3"} or {"python3"}.
func findPython3Command() ([]string, error) {
    // helper to test a command and args
    test := func(cand []string) bool {
        prog := cand[0]
        args := append(cand[1:], "-c", "import sys;print(sys.version_info[0])")
        cmd := exec.Command(prog, args...)
        out, err := cmd.Output()
        if err != nil {
            return false
        }
        v := strings.TrimSpace(string(out))
        return strings.HasPrefix(v, "3")
    }

    candidates := [][]string{}
    if strings.HasPrefix(strings.ToLower(os.Getenv("OS")), "windows") || os.PathSeparator == '\\' {
        candidates = [][]string{{"py", "-3"}, {"python"}, {"python3"}}
    } else {
        candidates = [][]string{{"python3"}, {"python"}}
    }
    for _, cand := range candidates {
        if test(cand) {
            return cand, nil
        }
    }
    return nil, fmt.Errorf("no python3 found in PATH (tried common names)")
}

func main() {
    owner := flag.String("owner", "JoaoAndrad", "GitHub owner/user")
    repo := flag.String("repo", "DashboardAutomatizadoMoodar", "GitHub repo name")
    project := flag.String("project", ".", "Path to project root to update")
    assetPrefix := flag.String("asset", "project-", "Asset name prefix to look for in the release (zip)")
    auto := flag.Bool("auto", false, "Apply update automatically (no prompt)")
    flag.Parse()

    // Ensure there's a resident launcher in Documents\Moodinho and delegate to it
    ensureResidentLauncher()

    // If project was not provided (default "."), use the resident Documents/Moodinho/project
    if *project == "." || strings.TrimSpace(*project) == "" {
        docs := getUserDocumentsDir()
        *project = filepath.Join(docs, "Moodinho", "project")
    }

    apiURL := fmt.Sprintf("https://api.github.com/repos/%s/%s/releases/latest", *owner, *repo)
    fmt.Printf("Launcher: checking releases for %s/%s...\n", *owner, *repo)
    body, err := httpGet(apiURL)
    if err != nil {
        fmt.Fprintf(os.Stderr, "failed to fetch release info: %v\n", err)
        os.Exit(1)
    }
    var rel githubRelease
    if err := json.Unmarshal(body, &rel); err != nil {
        fmt.Fprintf(os.Stderr, "failed to parse release JSON: %v\n", err)
        os.Exit(1)
    }
    fmt.Printf("Found release: %s\n", rel.TagName)

    asset := findAsset(rel.Assets, *assetPrefix)
    if asset == nil {
        fmt.Fprintf(os.Stderr, "no asset with prefix '%s' found in release\n", *assetPrefix)
        os.Exit(1)
    }

    tmpDir, err := ioutil.TempDir("", "moodar-update-")
    if err != nil {
        fmt.Fprintf(os.Stderr, "failed to create temp dir: %v\n", err)
        os.Exit(1)
    }
    defer os.RemoveAll(tmpDir)

    zipPath := filepath.Join(tmpDir, asset.Name)
    fmt.Printf("Downloading %s to %s...\n", asset.BrowserDownloadURL, zipPath)
    if err := downloadFile(zipPath, asset.BrowserDownloadURL); err != nil {
        fmt.Fprintf(os.Stderr, "download failed: %v\n", err)
        os.Exit(1)
    }

    // Try to find a checksum asset with same name + .sha256
    checksumAssetName := asset.Name + ".sha256"
    var checksumURL string
    for _, a := range rel.Assets {
        if a.Name == checksumAssetName {
            checksumURL = a.BrowserDownloadURL
            break
        }
    }
    if checksumURL != "" {
        fmt.Printf("Found checksum asset (%s), downloading...\n", checksumAssetName)
        csb, err := httpGet(checksumURL)
        if err != nil {
            fmt.Fprintf(os.Stderr, "failed to download checksum: %v\n", err)
            os.Exit(1)
        }
        expected := strings.Fields(string(csb))[0]
        fmt.Printf("Verifying sha256...\n")
        if err := verifySha256(zipPath, expected); err != nil {
            fmt.Fprintf(os.Stderr, "checksum verification failed: %v\n", err)
            os.Exit(1)
        }
        fmt.Printf("Checksum OK\n")
    } else {
        fmt.Printf("No checksum asset found; skipping verification\n")
    }

    // Extract to temp folder and atomically replace
    extractDir := filepath.Join(tmpDir, "extract")
    if err := unzip(zipPath, extractDir); err != nil {
        fmt.Fprintf(os.Stderr, "failed to extract zip: %v\n", err)
        os.Exit(1)
    }

    backupDir := *project + "-bak-" + strings.ReplaceAll(rel.TagName, "/", "-")
    fmt.Printf("Prepared extracted files in %s\n", extractDir)

    if !*auto {
        fmt.Printf("About to replace project at '%s' with release %s. Backup will be created at '%s'. Continue? (y/N): ", *project, rel.TagName, backupDir)
        var resp string
        fmt.Scanln(&resp)
        if strings.ToLower(strings.TrimSpace(resp)) != "y" {
            fmt.Println("Aborted by user")
            os.Exit(0)
        }
    }

    // Decide how to install the extracted files.
    // If the project path doesn't exist, rename extract -> project path.
    // If the project path exists and looks like a full project (indicators),
    // create a backup and replace it. If the project path exists but does NOT
    // look like a project (e.g. only has the launcher binary), move the
    // extracted contents into the existing directory so the launcher can
    // bootstrap itself in an empty folder.
    if !pathExists(*project) {
        if err := os.Rename(extractDir, *project); err != nil {
            fmt.Fprintf(os.Stderr, "failed to move new project into place: %v\n", err)
            os.Exit(1)
        }
    } else {
        // project path exists
        if hasProjectIndicators(*project) {
            fmt.Printf("Creating backup: %s\n", backupDir)
            if err := os.RemoveAll(backupDir); err != nil {
                fmt.Fprintf(os.Stderr, "failed removing old backup: %v\n", err)
                os.Exit(1)
            }
            if err := os.Rename(*project, backupDir); err != nil {
                fmt.Fprintf(os.Stderr, "failed to create backup: %v\n", err)
                os.Exit(1)
            }
            if err := os.Rename(extractDir, *project); err != nil {
                fmt.Fprintf(os.Stderr, "failed to move new project into place: %v\n", err)
                // Attempt rollback
                fmt.Fprintf(os.Stderr, "attempting rollback...\n")
                _ = os.Rename(backupDir, *project)
                os.Exit(1)
            }
        } else {
            // existing folder but no project indicators: merge contents
            if err := moveContents(extractDir, *project); err != nil {
                fmt.Fprintf(os.Stderr, "failed to install files into existing directory: %v\n", err)
                os.Exit(1)
            }
        }
    }

    fmt.Printf("Update applied. Starting project using scripts/start_server.py\n")
    // Prefer to use the project's venv python if present (project/.venv)
    var pythonCmd []string
    venvPy := filepath.Join(*project, ".venv")
    if os.PathSeparator == '\\' {
        venvPy = filepath.Join(*project, ".venv", "Scripts", "python.exe")
    } else {
        venvPy = filepath.Join(*project, ".venv", "bin", "python")
    }
    if pathExists(venvPy) {
        pythonCmd = []string{venvPy}
    } else {
        pc, err := findPython3Command()
        if err != nil {
            fmt.Fprintf(os.Stderr, "no suitable Python 3 interpreter found: %v\n", err)
            os.Exit(1)
        }
        pythonCmd = pc
    }

    // Build exec.Command safely with program and args
    cmd := exec.Command(pythonCmd[0], append(pythonCmd[1:], "scripts/start_server.py")...)
    // Ensure the start script runs with the project folder as working directory
    cmd.Dir = *project
    cmd.Stdout = os.Stdout
    cmd.Stderr = os.Stderr
    cmd.Stdin = os.Stdin
    if err := cmd.Run(); err != nil {
        fmt.Fprintf(os.Stderr, "failed to start project: %v\n", err)
        os.Exit(1)
    }
}
