# 困った時
| 出たこと | すること |
|---|---|
| ffmpeg: ありません | `bash tools/setup.sh`。Codex は環境の Install script（旧名 Setup script） に書く |
| 日本語フォント: ありません | `apt-get install -y fonts-noto-cjk` |
| apt-get が通らない（Claude） | 環境の Network access が None になっていないか。Limited（既定）に戻す |
| 動画がありません | 本人に inbox に入れたか聞く → `git pull` |
| 字幕がずれる | 字幕は原稿の文から作り、声のある長さで割っています。原稿と違うことを話した場面は、原稿をその通りに直して作り直す |
| 1本だけで場面に分かれない | 場面の間を2秒あけて撮り直すか、プロンプターで場面ごとに撮る |
| 100MB を超えた | `kata/kataN.json` の crf を 26〜28 に |
| Upload で 25MB を超える | 場面ごとに撮る（プロンプターは場面ごとに1本） |
