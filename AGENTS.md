# AGENTS.md — 開発メモ（エージェント・開発者向け）

このリポジトリを変更する人向けの記録です。使い方は [README.md](README.md)、対応機種と ROM の注意は [manual.md](manual.md) を参照してください。
ここには、コードを読んでも分かりにくい **設計の理由・調べて分かった事実・つまずきどころ・検証方法** を残します。

## 概要

ゲーム&ウオッチ（ゼルダ / マリオ）を「純正ファーム + Retro-Go」のデュアルブートにする、Windows 用の GUI（Python / Tkinter）です。
上流の 2 つのプロジェクトを `workspace\` にクローンし、ビルドした結果を gnwmanager（OpenOCD / ST-Link）で書き込みます。

- 純正側: [BrianPugh/game-and-watch-patch](https://github.com/BrianPugh/game-and-watch-patch)（`main`）
- エミュレータ: [sylverb/game-and-watch-retro-go](https://github.com/sylverb/game-and-watch-retro-go)（既定ブランチ `msx_wsv_genesis`、サブモジュールあり）

UI の文言・コメントは日本語です。

## 起動と実行環境

- 起動: `python -m gnwtool`（または `GnW改造ツール起動.bat` / デスクトップのショートカット）
- GUI は **システムの Python** で動きます（tkinter が必要。カバー編集には Pillow も必要）。ビルド用の依存は `tools\venv` に分けています。
- `.bat` は **cp932・CRLF** で保存すること（cmd は日本語を Shift-JIS で読むため）。日本語の文字列を cmd から PowerShell に渡すと文字化けするので、ショートカットは `gnwtool/shortcut.py` から PowerShell の `-EncodedCommand`（UTF-16）で作っています。

## モジュール構成

| ファイル | 役割 |
|---|---|
| `config.py` | パス、機種の定義（`DEVICES`: 純正の SHA1・容量・配色）、`Settings`（`settings.json` への保存、旧形式からの移行）、パッチ引数と Retro-Go の make 変数の組み立て |
| `toolchain.py` | ツールの検出と自動導入（Git Bash / make / ARM GCC / OpenOCD / venv）、`build_env()`、バックアップの検証、`roms\` → `workspace\...\roms\` の同期 |
| `capacity.py` | ROM フォルダから外部フラッシュの使用量を見積もる（実ビルドと照合済み）。FDS / MSX BIOS の検証、カバー画像の検出 |
| `package.py` | ビルド結果を `.gnw`（zip）にまとめる、検証する、書き込みコマンドを組み立てる。セーブ位置の取得（ELF + gdb）と、吸い出し / 書き戻しのコマンド |
| `cover_editor.py` | カバーのトリミング画面（貼り付け、4:3 固定、余白: 黒 / 白 / ぼかし / 配色の背景色） |
| `app.py` | Tkinter の画面（① 環境 ② バックアップ ③ 構成 ④ ROM と容量 ⑤ ビルド & 書き込み）と、処理の実行（ワーカースレッド + ログ） |
| `shortcut.py` | デスクトップにショートカットを作る |

## Windows でのビルド環境（WSL / Docker は使わない）

- **シェル**: Git for Windows の `usr\bin\bash.exe`。PATH は `build_env()` で Windows 形式で渡すと、msys が変換します。
- **make**: MSYS2 の `make-4.4.1-2-x86_64.pkg.tar.zst` から `make.exe` だけを取り出して `tools\bin\` に置きます。Git 同梱の `msys-2.0.dll` で動きます。zst の展開は venv の `zstandard` で行います。
- **シム**（`tools\bin\`）: Makefile は `python3` と `wget` を呼ぶので、`python3`（venv の python を実行）と `wget`（curl で代用）を置いています。
- **ARM GCC は 10〜14 系**を使います。15 は C23 が既定になり、古いコードが壊れるので避けます。見つからなければ xPack 14.2.1 を入れます。
- **OpenOCD**: `gnwmanager install openocd` は Windows では choco が必要なので使えません。xPack 版（0.12.0-7）を `tools\openocd\` に入れて PATH に通しています。gnwmanager は環境変数 `OPENOCD` か PATH から探します。

## 書き込み先の割り当て（最重要）

| 機種 / 構成 | 純正パッチ | Retro-Go 外部フラッシュ |
|---|---|---|
| ゼルダ 4MB（純正チップ） | `--device=zelda --no-la --no-sleep-images` | `EXTFLASH_SIZE=1794048 EXTFLASH_OFFSET=860160` |
| ゼルダ 増設（例 64MB） | `--device=zelda`（外部 0〜4MB を使う） | `EXTFLASH_SIZE=(MB-4)MB EXTFLASH_OFFSET=4194304` |
| マリオ（既定） | `--device=mario --internal-only`（内部 Bank1 に 256KB、外部は使わない） | オフセット 0、容量全体 |
| マリオ 増設 + 隠し要素を残す | `--device=mario`（外部 0〜1MB を使う） | オフセット 1MB |

Retro-Go は常に `INTFLASH_BANK=2`（0x08100000）で、`GNW_TARGET` は機種に合わせます（配色とボタン割り当てが変わる）。
`--internal-only` のときは外部フラッシュ用の出力が 0 バイトになるので、空のファイルは書き込みません。

## 書き込みの流れと .gnw パッケージ

1. ビルド（パッチ: `make PATCH_PARAMS=... patch` / Retro-Go: `make <vars>`）
2. `package.create()` で `builds\*.gnw` を作る。中身は、純正の int/ext、Retro-Go の intflash/extflash/ELF、`manifest.json`（機種・書き込み位置・ROM 一覧・SHA256）。
3. 書き込みは必ず `.gnw` を展開して SHA256 を検証し、`package.check()` で今の設定と合うか調べてから行う（機種 / オフセット / 容量が合わなければ拒否）。
4. gnwmanager の **1 回の接続**で、選んだ領域をまとめて書く（`flash ext … -- flash bank1 … -- flash 0x08100000 … -- flash ext … --offset=N -- start …`）。その後、OpenOCD で `reset_dbgmcu`（`mww 0x5C001004 0`）を実行する。
5. 成功したら `settings.last_written[device]` にパッケージ名を記録する（★表示とセーブの処理に使う）。

調べて分かったこと:
- **③（intflash）と④（extflash）は分けられません。** ROM 一覧表（`nes_roms` など）は intflash の .rodata にあり、ROM を 1 本足すと intflash も変わります。④だけ書くと起動しなくなります。
- gnwmanager の外部フラッシュ書き込みは、256KB 単位で本体と SHA256 を比べ、違う部分だけを消して書きます。消すのは書く範囲だけです。
- 上流の make 書き込みターゲットは使っていません（同じ内容を自前で組み立てています）。上流で書き込み手順が変わったら、`package.flash_command()` を見直してください。

## セーブデータ

- 位置はビルドごとに決まり、ELF の `<emu>_roms[i].save_address / save_size` で分かります。`package.save_slots()` は `arm-none-eabi-gdb --batch` で読みます（存在しない配列でエラーが出ても、後続の `-ex` は実行されます）。
- 配列名とセーブシンボル名の対応: `sg` の配列は `sg_roms`、セーブは `SAVE_SG1000_`。上流の `saves_backup.sh` は col / sg を対象にしていませんが、このツールでは扱います。
- 吸い出しは `gnwmanager dump 0x9xxxxxxx --dst … --size …`、書き戻しは `gnwmanager flash ext … --offset=(addr-0x90000000)`。ROM 名で対応付けるので、ROM 構成が変わっても引き継げます。
- **このツールで一度も書き込んでいない本体は、いま動いているビルドの ELF が無いので、セーブの位置が分かりません**（初回の書き込み時に警告します）。

## 容量計算のモデル（capacity.py）

実ビルドの結果（`scripts/extflash_size.sh` の出力と ELF のシンボル）と、バイト単位で一致することを確認済みです。

- 使用量 = 固定データ + エミュレータのコード + ROM データ + カバー画像
  - 固定データ = `align4K(4 + フォント + NES なら 40252 + SMS 系なら 8192)`。日本語フォント（CODEPAGE=932）は 212816。**機種（ゼルダ / マリオ）では変わりません**（以前「マリオはロゴ分 8KB 少ない」と書いたのは誤りでした）。
  - エミュレータのコード: `EMU_CODE`（ELF の `.overlay_*` セクションで LMA が 0x9xxxxxxx のもの）。MSX と Amstrad は BIOS 等が無いと計測できないので推定値です。
  - ROM データ: 圧縮する機種は `parse_roms.py` と同じ LZMA 設定（FORMAT_ALONE、preset 6、dict 16KB、ヘッダ 13 バイトを除く）。GB は先頭バンク以外を 16KB ごとに圧縮します。SMS / GG / MD / COL / SG / GW は非圧縮です。
  - カバー: `write_covart` と同じ変換（RGB → LANCZOS で 128×96 → JPEG optimize）を venv の Pillow で行ったサイズ。`.img`（変換済み）はそのままのサイズ。
- 容量 = 割り当て - セーブ領域（ROM ごとに 4KB 単位）- 4KB（設定）-（スクリーンショット有効なら 150KB）

**Retro-Go を更新したら、この数値を計測し直すこと。** 方法: 機種ごとにダミー ROM を 1 本だけ入れてビルドし、`arm-none-eabi-objdump -t` の `__extflash_data_end__` / `__extflash_game_rom_start__` と、`-h` の `.overlay_*` のサイズを読みます。NES のダミーは iNES ヘッダが必要です（`nesmapper.py` が読むため）。

## つまずきどころ

- **ROM を消しても、`.lzma` などの派生ファイルが残るとビルドが壊れます**（元が無いのに圧縮版を使おうとする）。`sync_roms()` が派生ファイルごと消しています。
- ROM が 1 本も無いと、`parse_roms.py` がエラーになります。
- **MSX** は BIOS 7 ファイルを SHA1 で照合し、1 つでも違うと MSX は使えません。`PANASONICDISK_.rom` はビルド時に作られます（+16KB）。
- **FDS** の BIOS は `nes_bios\disksys.rom`（8192 バイト）の固定名です。
- `.md` はメガドライブの ROM の拡張子です（Markdown と間違えて除外しないこと）。`README.md` は名前で除外しています。
- `.ggcodes` / `.pceplus` / `.mcf` はチート用の付属ファイルで、ROM ではありません。
- 拡張子の大文字小文字は、Retro-Go 側で区別されません。
- gnwmanager の `flash` と `dump` は `--` でつなげて 1 回の接続にできます。
- バックアップの SHA1: ゼルダの外部フラッシュは `[0x20000:0x3254A0]` の範囲、マリオは末尾 8KB を除いた範囲で照合します（patch 側の定義と同じ）。
- パッチのビルドで `patches/keystone_cache.json` が更新されます。`git pull` の前に `git checkout -- .` で戻しています。

## 検証方法

- 構文チェック: `tools\venv\Scripts\python.exe -m py_compile gnwtool\*.py`
- GUI のテストは、スクリプトから `App()` を作り、`after()` で手順を進めながら `PIL.ImageGrab` で撮影して確認しています。その際は次の点に気をつけてください。
  - `config.ROMS` をテスト用のフォルダに差し替える（本物の `roms\` を汚さない）。
  - `messagebox` を差し替える（ダイアログで止まるため）。
  - `settings.json` は退避して、終わったら戻す。
  - クリップボードを使うテストは、利用者のクリップボードを上書きします。
- テスト後は `sync_roms()` を本物の `roms\` で実行し、`workspace\game-and-watch-retro-go\roms\` からダミーを消して、`git -C workspace\... status` がきれいなことを確かめる。
- シェルのヒアドキュメントに `\\n` を含む Python を書くと、改行に化けることがありました。複雑な置換は、Write でスクリプトファイルを作ってから実行します。
- **実機での書き込み・セーブの吸い出し / 書き戻し・reset_dbgmcu は、まだ ST-Link を接続して確認していません。** ST-Link 未接続時に安全に止まることだけを確認済みです。

## 利用者の環境（2026-09-28 時点）

- ゼルダ版: 外部フラッシュを 64MB に換装済み。すでにデュアルブート化済みだが、このツールでの書き込み記録はまだ無い。
- マリオ版: 純正バックアップあり。外部フラッシュの容量は未確認のため、既定は 1MB。
- ST-Link を使用。`roms\` には利用者の ROM が入っている（コミットしないこと）。
