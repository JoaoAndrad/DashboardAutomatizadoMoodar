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
    extractDir := filepath.Join(tmpDir, "extract")
    if err := unzip(zipPath, extractDir); err != nil {
        fmt.Fprintf(os.Stderr, "falha ao extrair o pacote: %v\n", err)
        os.Exit(1)
    }

    fmt.Printf("Arquivos preparados em %s\n", extractDir)

    // Determine currently applied tag (if any) and skip update when identical
    currentTagFile := filepath.Join(*project, ".moodinho_release")
    currentTag := ""
    if pathExists(currentTagFile) {
        if b, err := ioutil.ReadFile(currentTagFile); err == nil {
            currentTag = strings.TrimSpace(string(b))
        }
    }

    if currentTag == rel.TagName {
        fmt.Printf("Nenhuma atualização: já está na tag %s. Iniciando o projeto...\n", rel.TagName)
    } else {
        fmt.Printf("Atualização disponível (%s). Aplicando agora...\n", rel.TagName)

        // Ensure project directory exists
        if !pathExists(*project) {
            if err := os.Rename(extractDir, *project); err != nil {
                fmt.Fprintf(os.Stderr, "falha ao mover o novo projeto para o local: %v\n", err)
                os.Exit(1)
            }
        } else {
            // Preserve .venv if present by moving it to temp
            venvPath := filepath.Join(*project, ".venv")
            var venvBackupPath string
            if pathExists(venvPath) {
                venvBackupPath = filepath.Join(tmpDir, "venv-backup")
                _ = os.RemoveAll(venvBackupPath)
                if err := os.Rename(venvPath, venvBackupPath); err != nil {
                    if err := moveContents(venvPath, venvBackupPath); err != nil {
                        fmt.Fprintf(os.Stderr, "falha ao preservar o venv existente: %v\n", err)
                        os.Exit(1)
                    }
                }
            }

            // Remove everything in project (we'll restore .venv later)
            entries, err := ioutil.ReadDir(*project)
            if err != nil {
                fmt.Fprintf(os.Stderr, "falha ao listar o diretório do projeto: %v\n", err)
                os.Exit(1)
            }
            for _, e := range entries {
                _ = os.RemoveAll(filepath.Join(*project, e.Name()))
            }

            // Move extracted contents into project
            if err := moveContents(extractDir, *project); err != nil {
                fmt.Fprintf(os.Stderr, "falha ao instalar arquivos no projeto: %v\n", err)
                // attempt to restore venv backup
                if venvBackupPath != "" {
                    _ = os.Rename(venvBackupPath, venvPath)
                }
                os.Exit(1)
            }

            // Restore preserved venv
            if venvBackupPath != "" {
                target := filepath.Join(*project, ".venv")
                _ = os.RemoveAll(target)
                if err := os.Rename(venvBackupPath, target); err != nil {
                    if err := moveContents(venvBackupPath, target); err != nil {
                        fmt.Fprintf(os.Stderr, "aviso: falha ao restaurar venv no novo projeto: %v\n", err)
                    }
                    _ = os.RemoveAll(venvBackupPath)
                }
            }
        }

        // Record applied release tag (best-effort)
        _ = ioutil.WriteFile(currentTagFile, []byte(rel.TagName), 0o644)
        fmt.Printf("Atualização %s aplicada com sucesso.\n", rel.TagName)
    }
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
        if err := os.Rename(srcPath, dstPath); err == nil {
            continue
        }
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


func getUserDocumentsDir() string {
    if h, err := os.UserHomeDir(); err == nil {
        docs := filepath.Join(h, "Documents")
        if pathExists(docs) {
            return docs
        }
        return h
    }
    return "."
}


func ensureResidentLauncher() {
    exePath, err := os.Executable()
    if err != nil {
        return
    }
    exePath, _ = filepath.Abs(exePath)

    docs := getUserDocumentsDir()
    moodinhoDir := filepath.Join(docs, "Moodinho")
    if err := os.MkdirAll(moodinhoDir, 0o755); err != nil {
        return
    }

    ext := filepath.Ext(exePath)
    residentName := "moodinho-launcher" + ext
    residentPath := filepath.Join(moodinhoDir, residentName)

    curClean, _ := filepath.Abs(exePath)
    resClean, _ := filepath.Abs(residentPath)
    if strings.EqualFold(curClean, resClean) {
        return
    }

    if err := copyFile(exePath, residentPath); err != nil {
        return
    }
    _ = os.Chmod(residentPath, 0o755)

    args := os.Args[1:]
    residentProject := filepath.Join(moodinhoDir, "project")

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

    _ = os.MkdirAll(residentProject, 0o755)

    cmd := exec.Command(residentPath, args...)
    cmd.Stdout = os.Stdout
    cmd.Stderr = os.Stderr
    cmd.Stdin = os.Stdin
    if err := cmd.Run(); err != nil {
        fmt.Fprintf(os.Stderr, "resident launcher failed: %v\n", err)
        os.Exit(1)
    }
    os.Exit(0)
}

func findPython3Command() ([]string, error) {
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

    fmt.Println("Olá, sou o Moodinho, deixa eu só verificar se tenho alguma atualização para você...")

    ensureResidentLauncher()

    if *project == "." || strings.TrimSpace(*project) == "" {
        docs := getUserDocumentsDir()
        *project = filepath.Join(docs, "Moodinho", "project")
    }

    apiURL := fmt.Sprintf("https://api.github.com/repos/%s/%s/releases/latest", *owner, *repo)
    fmt.Printf("Verificando atualizações para %s/%s...\n", *owner, *repo)
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
    fmt.Printf("Encontrada release: %s\n", rel.TagName)

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
    fmt.Printf("Baixando %s para %s...\n", asset.BrowserDownloadURL, zipPath)
    if err := downloadFile(zipPath, asset.BrowserDownloadURL); err != nil {
        fmt.Fprintf(os.Stderr, "download failed: %v\n", err)
        os.Exit(1)
    }

    checksumAssetName := asset.Name + ".sha256"
    var checksumURL string
    for _, a := range rel.Assets {
        if a.Name == checksumAssetName {
            checksumURL = a.BrowserDownloadURL
            break
        }
    }
    if checksumURL != "" {
        fmt.Printf("Encontrado asset de checksum (%s), baixando...\n", checksumAssetName)
        csb, err := httpGet(checksumURL)
        if err != nil {
            fmt.Fprintf(os.Stderr, "falha ao baixar checksum: %v\n", err)
            os.Exit(1)
        }
        expected := strings.Fields(string(csb))[0]
        fmt.Printf("Verificando sha256...\n")
        if err := verifySha256(zipPath, expected); err != nil {
            fmt.Fprintf(os.Stderr, "verificação do checksum falhou: %v\n", err)
            os.Exit(1)
        }
        fmt.Printf("Checksum OK\n")
    } else {
        fmt.Printf("Nenhum asset de checksum encontrado; pulando verificação\n")
    }

    extractDir := filepath.Join(tmpDir, "extract")
    if err := unzip(zipPath, extractDir); err != nil {
        fmt.Fprintf(os.Stderr, "falha ao extrair o pacote: %v\n", err)
        os.Exit(1)
    }

    fmt.Printf("Arquivos preparados em %s\n", extractDir)

    currentTagFile := filepath.Join(*project, ".moodinho_release")
    currentTag := ""
    if pathExists(currentTagFile) {
        if b, err := ioutil.ReadFile(currentTagFile); err == nil {
            currentTag = strings.TrimSpace(string(b))
        }
    }

    if currentTag == rel.TagName {
        fmt.Printf("Nenhuma atualização encontrada (tag %s). Iniciando o projeto...\n", rel.TagName)
    } else {
        fmt.Printf("Atualização disponível: %s -> aplicando agora...\n", rel.TagName)

        if !pathExists(*project) {
            if err := os.Rename(extractDir, *project); err != nil {
                fmt.Fprintf(os.Stderr, "falha ao mover o novo projeto para o local: %v\n", err)
                os.Exit(1)
            }
        } else {
            venvPath := filepath.Join(*project, ".venv")
            var venvBackupPath string
            if pathExists(venvPath) {
                venvBackupPath = filepath.Join(tmpDir, "venv-backup")
                _ = os.RemoveAll(venvBackupPath)
                if err := os.Rename(venvPath, venvBackupPath); err != nil {
                    if err := moveContents(venvPath, venvBackupPath); err != nil {
                        fmt.Fprintf(os.Stderr, "falha ao preservar o venv existente: %v\n", err)
                        os.Exit(1)
                    }
                }
            }

            entries, err := ioutil.ReadDir(*project)
            if err != nil {
                fmt.Fprintf(os.Stderr, "falha ao listar diretório do projeto: %v\n", err)
                os.Exit(1)
            }
            for _, e := range entries {
                name := e.Name()
                if name == ".venv" {
                    continue
                }
                _ = os.RemoveAll(filepath.Join(*project, name))
            }

            if err := moveContents(extractDir, *project); err != nil {
                fmt.Fprintf(os.Stderr, "falha ao instalar arquivos no projeto: %v\n", err)
                if venvBackupPath != "" {
                    _ = os.Rename(venvBackupPath, venvPath)
                }
                os.Exit(1)
            }

            if venvBackupPath != "" {
                target := filepath.Join(*project, ".venv")
                _ = os.RemoveAll(target)
                if err := os.Rename(venvBackupPath, target); err != nil {
                    if err := moveContents(venvBackupPath, target); err != nil {
                        fmt.Fprintf(os.Stderr, "aviso: falha ao restaurar venv no novo projeto: %v\n", err)
                    }
                    _ = os.RemoveAll(venvBackupPath)
                }
            }
        }


        _ = ioutil.WriteFile(currentTagFile, []byte(rel.TagName), 0o644)
        fmt.Printf("Atualização %s aplicada com sucesso.\n", rel.TagName)
    }

    fmt.Printf("Atualização aplicada. Iniciando o projeto usando scripts/start_server.py\n")

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
            fmt.Fprintf(os.Stderr, "nenhum interpretador Python 3 encontrado no PATH: %v\n", err)
            os.Exit(1)
        }
        pythonCmd = pc
    }


    if !pathExists(venvPy) {
        fmt.Printf("Preparando ambiente (criando venv em %s) ...\n", filepath.Dir(venvPy))
        createArgs := append(pythonCmd[1:], "-m", "venv", filepath.Join(*project, ".venv"))
        createCmd := exec.Command(pythonCmd[0], createArgs...)
        createCmd.Stdout = os.Stdout
        createCmd.Stderr = os.Stderr
        if err := createCmd.Run(); err != nil {
            fmt.Fprintf(os.Stderr, "falha ao criar venv em %s: %v\n", *project, err)
        } else {
            if pathExists(venvPy) {
                pythonCmd = []string{venvPy}
            }
        }
    }


    cmd := exec.Command(pythonCmd[0], append(pythonCmd[1:], "scripts/start_server.py")...)
    cmd.Dir = *project
    cmd.Stdout = os.Stdout
    cmd.Stderr = os.Stderr
    cmd.Stdin = os.Stdin
    if err := cmd.Run(); err != nil {
        fmt.Fprintf(os.Stderr, "falha ao iniciar o projeto: %v\n", err)
        os.Exit(1)
    }
}
