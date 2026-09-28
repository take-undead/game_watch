# チートコード（cheat_code）

`cheat_code\<機種>\<ROMと同じ名前>.ggcodes` に置いたチートは、ビルド時に同じ名前の ROM の隣へ自動でコピーされます。
使うには、③構成で **「チートコード対応」をオン** にしてビルドし、書き込みます。実機では、ゲーム選択画面の **「Cheat Codes」** で、使うコードを ON / OFF します。

## ファミコン（nes）: 自動で作ったもの

`roms\nes` の 68 本のうち **61 本** のチートを作りました（作成: 2026-09-28、`scripts\nes_cheats.py`）。

**日本版 ROM であることが前提です。** ネット上のゲームジニーのコードは、ほとんどが北米版向けです。そのため、集めたコードを 1 本ずつ手元の日本版 ROM と照合し、根拠のあるものだけを残しています。

| 判定 | 意味 |
|---|---|
| 照合済み | 8 文字のゲームジニーコードで、「書き換え前の値」が手元の ROM の該当番地と一致した（バンク配置を考慮） |
| 根拠あり | 6 文字コードで、手元の ROM の該当番地に「置き換え元として典型的な命令」があった（例: 残機を減らす DEC を読むだけの LDA に置き換える） |
| 出典のみ | 日本版（または日米共通版）向けとして公開されているコード。RAM を書き換えるコードなど、ROM と照合できないもの |

北米版のコードで手元の ROM と値が合わないものは、除外しました。同じゲームでも版（リビジョン）が違うと合わないことがあります。たとえばイー・アル・カンフーでは、Rev 1.2 用のコードはすべて不一致で、Rev 1.4 用だけが一致しました。

| ゲーム | ファイル | 件数 | 照合済み | 根拠あり | 出典のみ | 出典 |
|---|---|---|---|---|---|---|
| けっきょく南極大冒険 | `KEKYOKU.nes` | 10 | 5 | 0 | 5 | libretro: Kekkyoku Nankyoku Daibouken (Japan) |
| たけしの挑戦状 | `B_TAKESHI.nes` | 1 | 0 | 0 | 1 | libretro: Takeshi no Chousenjou (Japan) |
| イース | `YS1.nes` | 16 | 0 | 0 | 16 | libretro: Ys (Japan) |
| イースII | `YS2.nes` | 16 | 8 | 0 | 8 | libretro: Ys II - Ancient Ys Vanished - The Final Chapter (Japan) |
| イー・アル・カンフー | `KANFU.nes` | 5 | 3 | 0 | 2 | libretro: Yie Ar Kung-Fu (Japan) (Game Genie)<br>libretro: Yie Ar Kung-Fu (Japan) (Rev 1.4) |
| ギャラガ | `GALAGA.nes` | 12 | 12 | 0 | 0 | libretro: Galaga (Japan)<br>libretro: Galaga - Demons of Death (USA) (Game Genie) |
| クルクルランド | `Clu Clu Land.nes` | 16 | 6 | 1 | 9 | libretro: Clu Clu Land (World)<br>libretro: Clu Clu Land (World) (Game Genie) |
| グラディウス | `GRADIUS.nes` | 10 | 10 | 0 | 0 | libretro: Gradius (Japan)<br>libretro: Gradius (World) (Game Genie) |
| グラディウスII | `GRADIUS2.nes` | 16 | 7 | 0 | 9 | libretro: Gradius II (Japan)<br>libretro: Gradius II (Japan) (Game Genie) |
| グーニーズ | `goonies.nes` | 15 | 6 | 0 | 9 | libretro: Goonies (Japan) |
| グーニーズ2 | `goonies2.nes` | 9 | 9 | 0 | 0 | libretro: Goonies II, The (USA, Europe) (Game Genie) |
| ゲゲゲの鬼太郎 妖怪大魔境 | `gegege.nes` | 3 | 2 | 0 | 1 | libretro: Gegege no Kitarou - Youkai Daimakyou (Japan) |
| スカイキッド | `SKYKID.nes` | 14 | 10 | 0 | 4 | libretro: Sky Kid (USA)<br>libretro: Sky Kid (USA, Japan) (Game Genie) |
| スターソルジャー | `STAR_SOLDIER.nes` | 11 | 6 | 0 | 5 | libretro: Star Soldier (USA)<br>libretro: Star Soldier (USA, Japan) (Game Genie) |
| スターフォース | `STAR_FOACE.nes` | 2 | 2 | 0 | 0 | libretro: Star Force (Japan) |
| スター・ウォーズ (ナムコ) | `STAR_WARS.nes` | 16 | 6 | 0 | 10 | libretro: Star Wars (Japan) (Namco) |
| スパルタンX | `SPALTANX.nes` | 16 | 8 | 0 | 8 | libretro: Kung Fu (World) (Game Genie)<br>libretro: Spartan X (Japan) |
| スペランカー | `SPELUNKER.nes` | 10 | 7 | 1 | 2 | libretro: Spelunker (Japan)<br>libretro: Spelunker (USA, Japan) (Game Genie) |
| スーパーゼビウス ガンプの謎 | `S_XEVIOUS.nes` | 6 | 2 | 0 | 4 | libretro: Super Xevious - Gump no Nazo (Japan)<br>libretro: Super Xevious - Gump no Nazo (Japan) (Game Genie) |
| スーパーマリオブラザーズ | `S_MARIO.nes` | 16 | 16 | 0 | 0 | libretro: Super Mario Bros. (World) |
| スーパーマリオブラザーズ3 | `S_MARIO3.nes` | 16 | 16 | 0 | 0 | martaaay（北米版） |
| ゼビウス | `XEVIUS.nes` | 5 | 2 | 1 | 2 | libretro: Xevious (Japan) (En)<br>libretro: Xevious (Japan) (En) (Rev 1) |
| ゼルダの伝説 | `ZELDA.nes` | 16 | 16 | 0 | 0 | libretro: Legend of Zelda, The (USA, Europe) (Game Genie) |
| ソロモンの鍵 | `SOLOMON.nes` | 7 | 7 | 0 | 0 | libretro: Solomon's Key (USA, Europe) (Game Genie) |
| チャレンジャー | `CHALENGER.nes` | 6 | 6 | 0 | 0 | libretro: Challenger (Japan)<br>libretro: Challenger (Japan) (Game Genie) |
| テグザー | `THEXDER.nes` | 8 | 2 | 1 | 5 | libretro: Thexder (Japan) |
| テラクレスタ | `TERRA_CRESTA.nes` | 4 | 0 | 0 | 4 | libretro: Terra Cresta (USA) |
| ディグダグ | `DIG_DUG.nes` | 8 | 4 | 0 | 4 | libretro: Dig Dug (Japan)<br>libretro: Dig Dug (Japan) (Game Genie) |
| ディグダグII | `DIG_DUG2.nes` | 10 | 9 | 0 | 1 | libretro: Dig Dug II (Japan)<br>libretro: Dig Dug II - Trouble in Paradise (USA) (Game Genie) |
| デビルワールド | `DEVIL_WORLD.nes` | 1 | 0 | 0 | 1 | libretro: Devil World (Japan) (Rev 1) |
| ドラゴンクエスト | `DRAGON_QUEST.nes` | 8 | 0 | 0 | 8 | ファミコンチート集 Wiki |
| ドラゴンクエストII | `DRAGON_QUEST2.nes` | 6 | 6 | 0 | 0 | martaaay（北米版） |
| ドラゴンクエストIII | `DRAGON_QUEST3.nes` | 5 | 5 | 0 | 0 | martaaay（北米版） |
| ドラゴンスレイヤーIV | `DRAGON_SLAYER4.nes` | 3 | 3 | 0 | 0 | libretro: Legacy of the Wizard (USA) (Game Genie) |
| ドルアーガの塔 | `DRUAGA.nes` | 8 | 1 | 2 | 5 | libretro: Druaga no Tou (Japan) |
| ドンキーコング | `DONKEEY_KONG.nes` | 4 | 3 | 0 | 1 | libretro: Donkey Kong (Japan)<br>libretro: Donkey Kong (World) (Game Genie) |
| ドンキーコング3 | `DONKEY3.nes` | 16 | 10 | 2 | 4 | libretro: Donkey Kong 3 (World)<br>libretro: Donkey Kong 3 (World) (Game Genie) |
| ドンキーコングJR. | `DONKEY_JR.nes` | 4 | 4 | 0 | 0 | libretro: Donkey Kong Jr. (Japan)<br>libretro: Donkey Kong Jr. (World) (Rev 1) |
| ナッツ&ミルク | `NATU-MILK.nes` | 3 | 2 | 0 | 1 | libretro: Nuts _ Milk (Japan)<br>libretro: Nuts _ Milk (Japan) (Game Genie) |
| バベルの塔 | `BABEL.nes` | 7 | 0 | 0 | 7 | libretro: Babel no Tou (Japan) |
| バルーンファイト | `BALLOON_FIGHT.nes` | 1 | 0 | 0 | 1 | libretro: Balloon Fight (Japan) |
| パックマン | `PACMAN.nes` | 5 | 3 | 0 | 2 | libretro: Pac-Man (Japan) (En) |
| ボコスカウォーズ | `BOKOSUKA.nes` | 1 | 0 | 0 | 1 | libretro: Bokosuka Wars (Japan) |
| ボンバーマン | `BOMBAERMAN.nes` | 15 | 11 | 0 | 4 | libretro: Bomber Man (Japan)<br>libretro: Bomberman (USA) (Game Genie) |
| マッピー | `MAPPY.nes` | 9 | 7 | 1 | 1 | libretro: Mappy (Japan) |
| レッキングクルー | `WRECKING_CREW.nes` | 16 | 5 | 2 | 9 | libretro: Wrecking Crew (World)<br>libretro: Wrecking Crew (World) (Game Genie) |
| ロマンシア | `ROMANCIA.nes` | 2 | 0 | 0 | 2 | libretro: Romancia (Japan) |
| ロードランナー | `LOAD_RUNNER.nes` | 6 | 6 | 0 | 0 | libretro: Lode Runner (Japan)<br>libretro: Lode Runner (USA, Japan) (Game Genie) |
| ワープマン | `WARPMAN.nes` | 1 | 0 | 1 | 0 | libretro: Warpman (Japan) |
| 北斗の拳 | `HOKUTO1.nes` | 3 | 3 | 0 | 0 | libretro: Hokuto no Ken (Japan) |
| 北斗の拳2 | `HOKUTO2.nes` | 4 | 4 | 0 | 0 | libretro: Hokuto no Ken 2 (Japan) |
| 影の伝説 | `KAGE_D.nes` | 2 | 2 | 0 | 0 | libretro: Legend of Kage, The (USA) (Game Genie) |
| 悪魔城ドラキュラ | `DRACULA.nes` | 16 | 15 | 0 | 1 | libretro: Akumajou Dracula (Japan) |
| 機動戦士Zガンダム ホットスクランブル | `ZGUNDAM.nes` | 5 | 0 | 0 | 5 | libretro: Kidou Senshi Z Gundam - Hot Scramble (Japan) |
| 沙羅曼蛇 | `SARAMANDA.nes` | 9 | 4 | 0 | 5 | libretro: Salamander (Japan) |
| 超惑星戦記メタファイト | `META_FIGHT.nes` | 7 | 6 | 0 | 1 | libretro: Chou-Wakusei Senki - MetaFight (Japan) |
| 超時空要塞マクロス | `MACROSS.nes` | 5 | 4 | 0 | 1 | libretro: Choujikuu Yousai - Macross (Japan) |
| 迷宮組曲 | `MEIKYU.nes` | 2 | 0 | 0 | 2 | libretro: Meikyuu Kumikyoku - Milon no Daibouken (Japan) |
| 闘いの挽歌 | `TATAKAI.nes` | 3 | 3 | 0 | 0 | libretro: Tatakai no Banka (Japan) (Game Genie)<br>martaaay（北米版） |
| 魔城伝説II 大魔司教ガリウス | `GARIUS2.nes` | 2 | 0 | 0 | 2 | libretro: Majou Densetsu II - Daimashikyou Galious (Japan) |
| 魔界村 | `MAKAIMURA.nes` | 13 | 13 | 0 | 0 | libretro: Makaimura (Japan)<br>martaaay（北米版） |

### コードが無いもの（7 本）

| ゲーム | ファイル | 理由 |
|---|---|---|
| さんまの名探偵 | `SANMA.nes` | コードが見つかりませんでした（アドベンチャーゲーム） |
| オホーツクに消ゆ | `Okhotsk ni Kiyu.nes` | コードが見つかりませんでした（アドベンチャーゲーム） |
| サラダの国のトマト姫 | `saradanokuni.nes` | 北米版のコードが日本版と一致しませんでした（アドベンチャーゲーム） |
| ドラえもん | `DRAEMON.nes` | 日本版向けのコードが見つかりませんでした（Wiki はアクセス制限で未確認） |
| ハイドライド・スペシャル | `HYDLIDE.nes` | 北米版のコードが日本版（ハイドライド・スペシャル）と一致しませんでした |
| リップルアイランド | `LIPURU_ILAND.nes` | コードが見つかりませんでした |
| 戦場の狼 | `OOKAMI.nes` | 北米版（Commando）のコードが日本版と一致しませんでした |

## PCエンジン（pce）: 自動で作ったもの

`roms\pce` の 27 本のうち **20 本** のチートを作りました（作成: 2026-09-28、`scripts\pce_cheats.py`）。

PCエンジンのチートは `.pceplus` という **ROM パッチ形式**です（RAM を書き換えるコードは使えません）。書き換え前の値を持たないため、ファミコンのような 1 本ずつの照合はできません。代わりに次の方法で確かめています。

- **パッチ先の元の命令を調べました。** 正しい版の ROM なら、パッチ先は実際の命令の上にあり、典型的な改造の形になります。たとえば無限残機の多くは、「1 引いて書き戻す」（`E9 01 95 xx` = SBC #1 → STA）の書き戻しを、読むだけの命令（LDA）に置き換えるものでした。
- **ゲームごとの一致率が、ランダムな位置での割合の 2 倍以上（かつ 60% 以上）のものだけを採用しました。** 版が違う ROM では、パッチ先がでたらめなデータになるので、一致率が下がります。
- 元のファイルにある「Hacked Version」の行は、内容の説明が無いパッチなので除いています。
- 作ったファイルでビルドし、パッチの内容が正しく組み込まれることを確認済みです。

| ゲーム | ファイル | 件数 | 典型的な形のパッチ | ランダム時の割合 | 出典のファイル |
|---|---|---|---|---|---|
| グラディウス | `GRADIUS.pce` | 2 | 3/4 | 34% | Gradius (J) |
| サイドアーム | `SIDEARMS.pce` | 1 | 1/1 | 25% | Side Arms - Hyper Dyne (J) |
| サンダーブレード | `THANDER_BLADE.pce` | 1 | 1/1 | 24% | Thunder Blade (J) |
| スプラッターハウス | `SPLATTER_HOUSE.pce` | 2 | 3/3 | 19% | Splatterhouse (J) |
| スペースハリアー | `SPACH_HARRIER.pce` | 1 | 1/1 | 16% | Space Harrier (J) |
| スーパースターソルジャー | `STARTSOLDIER.pce` | 3 | 3/3 | 23% | Super Star Soldier (J) |
| ゼビウス ファードラウト伝説 | `XEVIOUS.pce` | 1 | 1/1 | 22% | Xevious - Fardraut Densetsu (J) |
| テラクレスタII | `TERRACRESTA2.pce` | 2 | 2/2 | 29% | Terra Cresta II - Mandrer no Gyakushuu (J) |
| ドラゴンスピリット | `DRAGON_SPIRIT.pce` | 2 | 3/3 | 24% | Dragon Spirit (J) |
| ドラゴンセイバー | `DRAGON_SABER.pce` | 2 | 3/3 | 26% | Dragon Saber - After Story of Dragon Spirit (J) |
| ニンジャウォーリアーズ | `NINJAWARRIORS.pce` | 1 | 2/2 | 25% | Ninja Warriors, The (J) |
| パックランド | `PACLAND.pce` | 1 | 1/1 | 19% | Pac-Land (J) |
| パロディウスだ! | `PARODIUS.pce` | 2 | 2/2 | 32% | Parodius Da! - Shinwa kara Owarai he (J) |
| ビックリマンワールド | `BIKURIMAN.pce` | 4 | 4/4 | 27% | Bikkuriman World (J) |
| ブラボーマン (北米版) | `Bravoman.pce` | 1 | 1/1 | 22% | Bravoman (U) |
| メルヘンメイズ | `MERUHEN.pce` | 2 | 2/2 | 29% | Marchen Maze (J) |
| ワルキューレの伝説 | `VALKYRIE.pce` | 2 | 2/2 | 28% | Valkyrie no Densetsu (J) |
| 出たな!!ツインビー | `D_TWIN_BEE.pce` | 1 | 1/1 | 27% | Detana!! TwinBee (J) |
| 妖怪道中記 | `YOUKAIDOU.pce` | 2 | 4/4 | 26% | Youkai Douchuuki (J) [h1] |
| 沙羅曼蛇 | `SARAMANDA.pce` | 3 | 3/3 | 30% | Salamander (J) |

### コードが無いもの（7 本）

| ゲーム | ファイル | 理由 |
|---|---|---|
| R-TYPE I | `R-TYPE1.pce` | コード集に「Hacked Version」（内容不明のパッチ）しかなかった |
| R-TYPE II | `R-TYPE2.pce` | コード集に「Hacked Version」（内容不明のパッチ）しかなかった |
| ドルアーガの塔 | `DRUAGA.pce` | コード集に「Hacked Version」（内容不明のパッチ）しかなかった |
| ワンダーモモ | `WANDA_MOMO.pce` | コード集に「Hacked Version」（内容不明のパッチ）しかなかった |
| 奇々怪界 | `KIKI.pce` | コード集に「Hacked Version」（内容不明のパッチ）しかなかった |
| 源平討魔伝 | `GENPEI.pce` | コード集に「Hacked Version」（内容不明のパッチ）しかなかった |
| （題名不明） | `MEZON.pce` | ROM から題名を特定できなかった |

## 注意

- **実機ではまだ試していません。** 「照合済み」でも、ゲームの進行によっては不具合が出ることがあります。おかしくなったら OFF にしてください。
- 1 本あたり最大 16 個です（Retro-Go の上限）。16 個を超える場合は、無敵・残機・体力・時間・武器などを優先し、同じ種類は最大 3 個までにしています。
- 説明文は英語です（最大 30 文字）。日本語にすると、メニュー言語を英語（CODEPAGE=1252）にしたときにビルドが失敗するためです。
- 使える形式（ファミコン）: ゲームジニー（6 / 8 文字）、`AAAA:VV`（RAM の値を固定）、`AAAA?CC:VV`（比較付き）。1 行に `+` で 3 つまでつなげられます。
- 使える形式（PCエンジン）: `.pceplus` の ROM パッチ。`01822fbd` なら「1 バイト / 番地 $1822F / 値 $BD」です。番地はヘッダ（512 バイト）を除いた位置で、1 行に複数並べられます。
- `#` で始まる行はコメントになりません（メニューに項目として表示されます）。

## 自分でコードを足す・作り直す

- ファイルを直接編集できます。書式は `コード, 説明` です（1 行 1 項目）。
- ROM を追加したときは、`scripts\nes_cheats.py`（ファミコン）/ `scripts\pce_cheats.py`（PCエンジン）の `MAP` に対応を書き足してから実行すると、作り直せます。

```
tools\venv\Scripts\python.exe scripts\nes_cheats.py
```

- 照合の詳細は `nes\report.json` にあります。

## 出典

- [libretro-database](https://github.com/libretro/libretro-database)（cht/Nintendo - Nintendo Entertainment System）
- [martaaay/game-and-watch-retro-go-game-genie-codes](https://github.com/martaaay/game-and-watch-retro-go-game-genie-codes)
- [ファミコンチート集 Wiki](https://wikiwiki.jp/nnnes1/)（ドラゴンクエスト）
- [olderzeus/game-genie-codes-nes](https://github.com/olderzeus/game-genie-codes-nes)（pceplus フォルダ。PCエンジン）
