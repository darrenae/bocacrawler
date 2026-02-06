# bocacrawler

BOCA 簽證網頁爬蟲與文字輸出工具。

## 用法

### 1) 既有模式（自動掃描列表並輸出更新內容）

```bash
python crawler.py
```

### 2) 自訂模式（使用者輸入網頁與輸出 txt，可多組）

每組 `--target` 需要兩個參數：`URL` 與 `OUTPUT_TXT`。

```bash
python crawler.py \
  --target "https://www.boca.gov.tw/cp-12-4486-0b0ec-1.html" output1.txt \
  --target "https://www.boca.gov.tw/cp-12-4517-c6f57-1.html" output2.txt
```

上述會將每個網頁分別輸出到對應的 txt 檔案（1 對 1）。

> 建議在 CI（例如 GitHub Actions）優先使用「單行指令」，可避免 shell 換行續接失敗：

```bash
python crawler.py --target "https://www.boca.gov.tw/cp-12-4486-0b0ec-1.html" output1.txt --target "https://www.boca.gov.tw/cp-12-4517-c6f57-1.html" output2.txt
```

### 常見錯誤：`--target: command not found`

當你在 shell 看到：

```text
line X: --target: command not found
```

通常是前一行的 `\` 沒有正確續行（例如 `\` 後面有空白、縮排/換行被 CI 改寫）。

可用以下任一做法避免：

1. 改用上方「單行指令」。
2. 若要多行，確保每一行結尾的 `\` 是該行最後一個字元（後面不能有空白）。
