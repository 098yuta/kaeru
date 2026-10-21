# KAERU

定価割れスニーカー、買える時代。

お気に入りのスニーカーのうち、選んだサイズの新品が国内定価を下回っているものだけを表示する静的サイトです。

- `index.html` … 画面（data.json を読んで表示）
- `data.json` … 価格データ
- `images/` … イラスト（品番.png）
- `add.txt` … 追加したい品番を1行ずつ書くと、次の週次更新で取り込み
- `scripts/update.py` … 週次更新（スニダンからサイズ別の新品最安値と定価を取得）
- `.github/workflows/update.yml` … 毎週月曜12:07（JST）に自動実行。Actions タブから手動実行も可
