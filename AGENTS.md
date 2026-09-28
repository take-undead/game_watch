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

### 持ち運び版（scripts/make_portable.py）

フォルダの中だけで完結し、フォルダごとコピーすれば別の PC でも動く版です。`python scripts\make_portable.py [出力先]` で作ります（既定はこのフォルダの隣の `game_watch_kai\`。何度実行してもよく、コピーは差分だけ）。

- **venv は使えません。** `pyvenv.cfg` が元の Python の場所を覚えているため、移すと動きません。代わりに、venv の元の Python 一式を `tools\python` にコピーし、venv の `site-packages` を重ねます。`config.PORTABLE`（`tools\python\python.exe` があるか）で切り替わり、`VENV_PY` / `VENV_SCRIPTS` がそちらを指します。
- **pip が作る `Scripts\*.exe`（gnwmanager.exe など）は python の絶対パスを埋め込んでいて、移すと動きません。** `write_shims()` が `tools\bin\gnwmanager`（`python -m gnwmanager`）と `python3` を、`tools\bin` からの相対パスで作ります（通常版でも同じシムを使う）。
- Git は PortableGit（`tools\git`、`find_git_root()` が最優先で探す）、ARM GCC は xPack（`tools\arm-gcc`、もともと同梱版を優先）。ダウンロードは元のフォルダの `tools\downloads` に残して再利用します。
- 起動用の `GnW改造ツール.exe` は、Windows 標準の `csc.exe`（.NET Framework 4）で `scripts\portable\launcher.cs` からビルドします。`tools\python\pythonw.exe -m gnwtool` を、`PYTHONNOUSERSITE=1` を付けて起動するだけです。`build_env()` も持ち運び版では `PYTHONNOUSERSITE=1` を付けます（その PC のユーザー用パッケージを混ぜない）。
- `settings.json` の `backup_dirs` は、ツールのフォルダ内なら相対パスで保存します（`Settings.save()` / `load()`）。
- PC ごとに要るのは ST-Link の USB ドライバだけです（Windows の仕組み上、持ち運べない）。
- 2026-09-28 に確認: PATH を `C:\Windows\System32` などだけにして、持ち運び版の中から `gnwmanager info`（ST-Link まで通信）と Retro-Go の実ビルドが通り、exe から画面が開きました。すべてのコマンドが持ち運び版の `tools\` から使われていました。

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
  - 固定データ = `align4K(4 + フォント + NES なら 40252 + SMS 系なら 8192 + MSX なら 262144)`。日本語フォント（CODEPAGE=932）は 212816。MSX の 262144 は YJK 色変換表 `msxYjkColor`、SMS 系の 8192 は `ColecoVision_BIOS` です。**機種（ゼルダ / マリオ）では変わりません**（以前「マリオはロゴ分 8KB 少ない」と書いたのは誤りでした）。
  - エミュレータのコード: `EMU_CODE`（ELF の `.overlay_*` セクションで LMA が 0x9xxxxxxx のもの）。NES（fceumm）は、使うマッパーの種類だけコードが増えます（0 番以外 1 種類あたり平均 `NES_MAPPER_CODE`=1110）。Amstrad だけは計測できていないので推定値です。CHEAT_CODES=1 では PCE がおよそ 100 バイト増えます（見積もりには含めていません）。
  - 2026-09-28 に、利用者の ROM 231 本（NES / PCE / SMS / MD / MSX / GW、カバーあり、日本語、チートあり）でビルドし、使用量の差は 100 バイトでした（容量は一致）。
  - ROM データ: 圧縮する機種は `parse_roms.py` と同じ LZMA 設定（FORMAT_ALONE、preset 6、dict 16KB、ヘッダ 13 バイトを除く）。GB は先頭バンク以外を 16KB ごとに圧縮します。SMS / GG / MD / COL / SG / GW は非圧縮です。
  - カバー: `write_covart` と同じ変換（RGB → LANCZOS で 128×96 → JPEG optimize）を venv の Pillow で行ったサイズ。`.img`（変換済み）はそのままのサイズ。
- 容量 = 割り当て - セーブ領域（ROM ごとに 4KB 単位）- 4KB（設定）-（スクリーンショット有効なら 150KB）

### 内部フラッシュの見積もり（capacity.estimate_intflash）

Retro-Go 本体は内部フラッシュ（`INTFLASH_BANK=2`、256KB）に入り、ここに ROM ごとの一覧表と表示名、チートも入ります。外部フラッシュに余裕があっても、ここが溢れるとリンクで `region FLASH overflowed` になります。

- 使用量 = 固定 `INTFLASH_FIXED` +（チート ON なら `INTFLASH_CHEAT_CODE`）+ 一覧表 + 文字列 + チートのポインタ
  - 一覧表: 1 本 44 バイト（`retro_emulator_file_t`、COVERFLOW=1）。チート ON で 60 バイト（`id` とポインタ 3 つ）なので、**チートの無い ROM も 16 バイト増えます**。COVERFLOW=0 では 8 バイト減ります。BIOS（`nes_bios` / `msx_bios`、ビルド時に作られる `PANASONICDISK_.rom` も）も 1 項目ずつ入ります。
  - 文字列: 表示名（`roms/<機種>.json` の name、無ければファイル名）、拡張子、チートのコードと説明。`.rodata.str1.4` なので 1 つずつ「終端込みで 4 バイト境界」、同じ文字列は 1 つにまとまります。PCエンジンのチートは `\x1\x00…` のエスケープで書かれるので、エスケープ 1 つを 1 バイトと数えます。
  - チートのポインタ: 1 個あたり 8 バイト（コードと説明の `const char*` 配列。.data なので RAM にも同じだけ入る）。件数の定数（`GG_NES_n_COUNT`）は最適化で消え、0 バイトです。
  - チートの読み取りと変換は、`parse_roms.py` をそのまま読み込んで `ROM(...).get_cheat_codes()` で行います（NES の大文字化、`.mcf` の「番地,値,長さ」への変換、`.pceplus` の変換が本物と同じになる）。`parse_roms.py` は標準ライブラリだけで動きますが、グローバルの `args.save` を参照するので、読み込んだあとに設定しています。
- 2026-09-28 に計測（ゼルダ / CODEPAGE=932 / COVERFLOW=1）: チート OFF 229,816 バイト（ELF から、固定 215,852）、チート ON 263,088 バイト（容量超過したビルドのリンクマップから、233 本・チート 113 本 745 個）で、見積もりは両方と一致しました。マリオや COVERFLOW=0 では、固定部分が少し違う可能性があります（未計測）。
- 計測し直す方法: チート OFF は ELF の `_sidata + (_edata - _sdata) - 0x08100000` が使用量で、`*_roms` シンボルの大きさと、各項目の `.name` の文字列から固定部分を逆算します。チート ON はリンクが失敗しても `build/gw_retro_go.map` が残るので、`.text` / `.rodata` / `.data`（load address）から使用量を出し、`rom_manager.o` の `.rodata.str1.4`・`*_roms`・`*_CODE_n` / `*_DESC_n` を合計して比べます。

**Retro-Go を更新したら、この数値を計測し直すこと。** 方法: 機種ごとにダミー ROM を 1 本だけ入れてビルドし、`arm-none-eabi-objdump -t` の `__extflash_data_end__` / `__extflash_game_rom_start__` と、`-h` の `.overlay_*` のサイズを読みます。NES のダミーは iNES ヘッダが必要です（`nesmapper.py` が読むため）。

## チート（cheat_code/ と scripts/nes_cheats.py）

- `cheat_code/<機種>/<ROM名>.ggcodes|.pceplus|.mcf` は、`sync_roms()` で同名 ROM の隣へコピーされます（`roms` 側に同名があれば、そちらを優先）。
- Retro-Go の NES チートは、ゲームジニー（6 / 8 文字）、`AAAA:VV`、`AAAA?CC:VV`、PAR を読みます（`main_nes_fceu.c` の `apply_cheat_code`）。1 本あたり最大 16 個です。`parse_roms.py` は `#` の行を読み飛ばしません。説明文は CODEPAGE で C ソースに書き出されるので、ASCII にしています。
- `scripts/nes_cheats.py` は、libretro-database と martaaay のコードを集め、**手元の日本版 ROM と照合して**から書き出します。
  - 8 文字コードは、比較値が PRG の該当番地（マッパーのバンク配置を考慮）にあるかで判定します。
  - 6 文字コードは、置換元の命令が典型パターン（DEC→LDA など）の場合だけ、北米版のものも採用します。
  - 日本版・日米共通版のファイルにある RAM コードは、出典を根拠に採用します。
  - 同じゲームでも版が違うと一致しません（例: イー・アル・カンフー Rev 1.2 と Rev 1.4）。題名が不明な ROM は、候補のコードの一致数や、ROM 内の製品番号（例: `RC802 1.4`）で特定しました。
- 出典は `scripts/download_cheats.py` で `tools\cache\cheatdb\` にまとめて落とせます（libretro-database はファミコン / FDS / PCE / MSX の `cht` だけを sparse checkout、martaaay と olderzeus と blueMSX は zip）。2 つのスクリプトは、ここを先に読み、無ければ 1 本ずつネットから取ります。martaaay には `Q*Bert.ggcodes` のように Windows で使えない名前があり、git checkout が止まるため、zip を展開するときに `_` に置き換えています。
- ファミコンチート集 Wiki（wikiwiki.jp）は、連続してアクセスすると 429 で拒否されます。メンテナンスで止まっていることもあります。
- 北米版と日本版で RAM の配置が違うゲームがあります（例: ハイドライド・スペシャルは北米版 Hydlide と別配置で、北米版の `0038` = 体力は日本版では経験値）。**まず日本のサイト（ファミコンチート集 Wiki）で日本版のコードを探す**こと（利用者の方針）。
- 出典のデータベースに無いゲームは、日本のサイトの RAM コードを `MANUAL` に手で書き、ROM でその番地がどう使われているかを確かめてから採用します。例: ハドソン版ドラえもんの Wiki の `002B-2-0020` は 2 バイトのリトルエンディアンで、`002B:20+002C:00` になります（ROM では体力の満タン = `(8 - $2C) * 4`）。
- PCエンジンの `.pceplus` は ROM パッチだけです（`main_pce.c` の `pce_rom_full_patch`）。ヘッダ（`len & 0x1FFF`）を除き、北米版のビット反転を解読した **後** の ROM_DATA に当たります。書式は 1 コマンド = `[バイト数-1:4bit][番地:20bit][データ]` の 16 進です。
- ディスクシステム（`.fds`）も `roms/nes` に置き、`.ggcodes` が効きます（FCEU のチートは読み出しの差し替えなので、RAM に読み込まれたプログラムにも効く）。`nes_cheats.py` の `FdsRom` は、各面のファイルヘッダ（ブロック 3）から読み込み先を取り、同じ番地に読み込むファイルが複数あれば全部を候補にします。$E000 以降は BIOS なので、そこを指すコード（北米カートリッジ版の流用）は除外します。ディスクから読み込まない $6000〜$DFFF は RAM です（例: メトロイドの FDS 版は、北米版 $6877〜 の変数が $B410〜 にある）。
- **チートは内部フラッシュを使います。** `parse_roms.py` は `const char* GG_NES_CODE_n[] = {"…"}` の形で書き出すので、文字列は .rodata、ポインタの配列は .data（どちらも intflash の 256KB）に入ります。目安は 1 コードあたり「コード + 説明の文字列 + 8 バイト」。2026-09-28 時点でチート全体は約 30KB（NES 22KB / PCE 1.4KB / MSX 6.8KB）で、利用者の ROM 構成（ROM 一覧表も intflash に入る）では `region FLASH overflowed by 600 bytes` になりました（その後、ハイドライド・スペシャル / 戦場の狼 / トマト姫の分で約 0.7KB 増えています）。利用者は、入れる ROM の数で調整する方針です。この超過は ④ の見積もり（`capacity.estimate_intflash`）で、ビルド前に分かります（下記「内部フラッシュの見積もり」）。
- **MSX** のチートは blueMSX の `.mcf`（`0,番地,値,0,説明`、10 進）です。Retro-Go は RAM の読み出しを差し替えます（`SlotManager.c` の `msxUpdateCheatInfo`）。値が 255 を超えると 2 バイト。`scripts/msx_cheats.py` は、MCF の番地を Z80 の命令（`LD A,(nn)` など）が直接参照している割合を、RAM のランダムな番地での割合と比べて版の一致を判定します。ランダム側の範囲を MCF の番地の範囲に絞ると、番地が 1〜2 個のファイルで割合が 100% になって誤判定するので、RAM 全体（$C000 / $E000〜$F37F）から取ります。出典の Cheats.zip は公式サイトが 404 で、archive.org の `web/2015id_/` から取れます。
- `scripts/pce_cheats.py` は、パッチ先の元の命令が典型的な改造の形（DEC/STA→LDA/LDX/CMP/NOP、分岐の変更、即値・書き込み先番地の変更）かどうかでゲームごとの一致率を出し、ランダムな位置での割合と比べます。判定の形が狭すぎると正しいコードを落とします（STA abs,Y→LDX abs,Y や DEC→CMP を加える前は、スプラッターハウスなどが落ちていました）。

## つまずきどころ

- **ROM を消しても、`.lzma` などの派生ファイルが残るとビルドが壊れます**（元が無いのに圧縮版を使おうとする）。`sync_roms()` が派生ファイルごと消しています。
- ROM が 1 本も無いと、`parse_roms.py` がエラーになります。
- **MSX** は BIOS 7 ファイルを SHA1 で照合し、1 つでも違うと MSX は使えません。`PANASONICDISK_.rom` はビルド時に作られます（+16KB）。
- **FDS** の BIOS は `nes_bios\disksys.rom`（8192 バイト）の固定名です。
- **ROM・カバーのファイル名に日本語などがあると、ビルドが失敗します。** `parse_roms.py` は Python の `isalnum()` で記号を `_` に置き換えますが、日本語はそのまま残ります。そのため C 側の識別子が壊れます（932 では EUC-JP のバイト列で `stray '¥'`、1252 ではエンコードエラー）。表示名は `roms/<機種>.json`（romdef 形式の `name`）で付けられ、CODEPAGE=932 なら日本語にできます。このファイルは `sync_roms()` が retro-go 側へ同期します。
- 読み取り専用属性の付いた ROM があると、コピー先も読み取り専用になり、次の同期で削除できません。同期ではコピー後に書き込み可能にしています。
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
- 2026-09-28: ゼルダ版（64MB）で、Retro-Go の書き込み・セーブの吸い出し（223 件）/ 書き戻し（213 件）・reset_dbgmcu まで実機で通りました。純正ファームの書き込みは未確認です。
- **gnwmanager のサブコマンドを 1 つにつなぎすぎると `[WinError 206] ファイル名または拡張子が長すぎます` になります**（Windows のコマンドラインは 32,767 文字まで）。セーブ 223 件の `dump` を 1 回にまとめたら超え、吸い出しの段階で失敗しました（書き込み前なので本体は無事）。`package._chain()` で 8,000 文字ごとに分けて、複数回の接続にしています。
- 2026-09-28: ST-Link V2（USB `VID_0483&PID_3748`）でゼルダ版に接続し、`gnwmanager info` が通りました（Stock Firmware: ZELDA / External Flash 64MB / UNLOCKED）。`Filesystem Size: MISSING/CORRUPT` は、gnwmanager が外部フラッシュの末尾に置くファイルシステムが無いという意味で、この Retro-Go（`msx_wsv_genesis`）では使わないので問題ありません。コマンド行から試すときは、`tools\openocd\*\bin` を PATH に入れ、`OPENOCD` にその `openocd.exe` を指定します。

## 利用者の環境（2026-09-28 時点）

- ゼルダ版: 外部フラッシュを 64MB に換装済み。すでにデュアルブート化済みだが、このツールでの書き込み記録はまだ無い。
- マリオ版: 純正バックアップあり。外部フラッシュの容量は未確認のため、既定は 1MB。
- ST-Link を使用。`roms\` には利用者の ROM が入っている（コミットしないこと）。
