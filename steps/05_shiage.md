# 5. 型で仕上げる（AI がする）
- `python3 tools/make.py --name <短い題>`
- 出来上がり：`out/<日付>_<題>/kansei.mp4` と `thumb.jpg`
- 確かめ方：`ffmpeg -i out/.../kansei.mp4 -vf fps=1/3,scale=360:-1,tile=4x1 -frames:v 1 /tmp/sheet.jpg` で並べて見る（画像を見られる AI は自分で見る）。字幕が切れている・帯が顔にかかる時は `kata/kataN.json` の数字を直して作り直す。
- 100MB を超えると GitHub に入らない。超えたら `kata/kataN.json` の crf を 26 に上げる。
