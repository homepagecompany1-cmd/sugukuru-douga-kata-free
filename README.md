# 動画の型1〜4（無料・スマホだけ）

スマホで撮った動画を、AI（Claude Code／Codex）が型どおりに仕上げます。撮る時は、原稿が画面に出るプロンプター付き。

## 始め方（3つ）
1. 右上の **Use this template** → **Private** で自分のリポを作る
2. Claude アプリの **Code** タブ（または ChatGPT の **Codex**）で、作ったリポを選ぶ
3. 「AGENTS.md を読んで、始めて」と送る

## 型
型1 撮るだけ（縦）／型2 対談（横）／型3 タイムスケジュール（黒い画面に時刻）／型4 年表・自己紹介（黒い画面に何年）

## 中身
- `tools/make.py` 仕上げ（ffmpeg＋Pillow だけ・外の API なし）
- `tools/url.py` 撮影プロンプターの URL を作る（原稿は URL の # より後ろ＝サーバーに届かない）
- `kata/` 型の見た目の数字　`steps/` 手順　`state/PROGRESS.md` 進み具合

## ご注意
- 結果（再生数・集客・売上）は保証しません。見た目は素材と環境で変わります。
- Claude Code は Claude の有料プラン（Pro 以上）、Codex は Codex が使える ChatGPT のプランが必要です。
- ライセンス：CC BY-NC 4.0（配布・改変OK・出どころを示す・商用利用不可）。`LICENSE.md`

2026年11月版 ／ すぐ来るたいき（ヨセカ）
