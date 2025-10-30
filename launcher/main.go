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

func main() {
    owner := flag.String("owner", "JoaoAndrad", "GitHub owner/user")
    repo := flag.String("repo", "DashboardAutomatizadoMoodar", "GitHub repo name")
    project := flag.String("project", ".", "Path to project root to update")
    assetPrefix := flag.String("asset", "project-", "Asset name prefix to look for in the release (zip)")
    auto := flag.Bool("auto", false, "Apply update automatically (no prompt)")
    flag.Parse()

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

    // Move current project to backup
    if _, err := os.Stat(*project); err == nil {
        fmt.Printf("Creating backup: %s\n", backupDir)
        if err := os.RemoveAll(backupDir); err != nil {
            fmt.Fprintf(os.Stderr, "failed removing old backup: %v\n", err)
            os.Exit(1)
        }
        if err := os.Rename(*project, backupDir); err != nil {
            fmt.Fprintf(os.Stderr, "failed to create backup: %v\n", err)
            os.Exit(1)
        }
    }

    // Move extracted to project path
    if err := os.Rename(extractDir, *project); err != nil {
        fmt.Fprintf(os.Stderr, "failed to move new project into place: %v\n", err)
        // Attempt rollback
        fmt.Fprintf(os.Stderr, "attempting rollback...\n")
        _ = os.Rename(backupDir, *project)
        os.Exit(1)
    }

    fmt.Printf("Update applied. Starting project using scripts/start_server.py\n")
    cmd := exec.Command("python", "scripts/start_server.py")
    cmd.Stdout = os.Stdout
    cmd.Stderr = os.Stderr
    cmd.Stdin = os.Stdin
    if err := cmd.Run(); err != nil {
        fmt.Fprintf(os.Stderr, "failed to start project: %v\n", err)
        os.Exit(1)
    }
}
