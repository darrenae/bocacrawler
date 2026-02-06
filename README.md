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
