# チートコード（cheat_code）

`cheat_code\<機種>\<ROMと同じ名前>.ggcodes` に置いたチートは、ビルド時に同じ名前の ROM の隣へ自動でコピーされます。
使うには、③構成で **「チートコード対応」をオン** にしてビルドし、書き込みます。実機では、ゲーム選択画面の **「Cheat Codes」** で、使うコードを ON / OFF します。

## ファミコン（nes）: 自動で作ったもの

`roms\nes` の 71 本のうち **67 本** のチートを作りました（作成: 2026-09-28、`scripts\nes_cheats.py`）。ディスクシステム（`.fds`）の 3 本も含みます。

**日本版 ROM であることが前提です。** ネット上のゲームジニーのコードは、ほとんどが北米版向けです。そのため、集めたコードを 1 本ずつ手元の日本版 ROM と照合し、根拠のあるものだけを残しています。

| 判定 | 意味 |
|---|---|
| 照合済み | 8 文字のゲームジニーコードで、「書き換え前の値」が手元の ROM の該当番地と一致した（バンク配置を考慮） |
| 根拠あり | 6 文字コードで、手元の ROM の該当番地に「置き換え元として典型的な命令」があった（例: 残機を減らす DEC を読むだけの LDA に置き換える） |
| 出典のみ | 日本版（または日米共通版）向けとして公開されているコード。RAM を書き換えるコードなど、ROM と照合できないもの |

ディスクシステム（`.fds`）では、ディスク上の各ファイルの読み込み先の番地を読み取り、同じ方法で照合しています。北米のカートリッジ版向けのコードは、FDS では BIOS の領域（$E000 以降）を指すことが多いので除外しました。

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
| ハイドライド・スペシャル | `HYDLIDE.nes` | 11 | 0 | 0 | 11 | ファミコンチート集 Wiki（下記） |
| 戦場の狼 | `OOKAMI.nes` | 4 | 0 | 0 | 4 | ファミコンチート集 Wiki（下記） |
| サラダの国のトマト姫 | `saradanokuni.nes` | 2 | 0 | 0 | 2 | ファミコンチート集 Wiki |
| なぞの村雨城 (FDS) | `nazo_mura.fds` | 4 | 1 | 0 | 3 | libretro: Nazo no Murasamejou (Japan) |
| メトロイド (FDS) | `metroid.fds` | 4 | 0 | 0 | 4 | libretro: Metroid (Japan) (v1.1) [b]<br>ROM で確認（下記） |
| リンクの冒険 (FDS) | `link.fds` | 5 | 0 | 0 | 5 | libretro: Link no Bouken - The Legend of Zelda 2 (Japan) |

- メトロイド（FDS）: 北米版の RAM コード（ミサイル `6879` など）は、FDS 版では番地が違います（$68xx は FDS 版ではプログラムの領域です）。ROM を調べてエネルギー（`0106` / `0107`、北米版と同じ）とミサイル（`B412` は発射で減る数、`B413` は上限）を確かめ、`Energy always 99` と `Infinite Missiles` を足しました。
- ハイドライド・スペシャル: 北米版 Hydlide とは RAM の配置が違う（北米版の `0038` = 体力は、日本版では経験値）ため、北米版のコードは使えません。ファミコンチート集 Wiki の日本版のコードを使い、ROM で確かめました（`0036` = LIFE で 0 ならゲームオーバー、`0039` = MAGIC、`007F` が 0 以外の間は MAGIC を 100 に保つ、`0026` が 0 以外なら被弾の処理を飛ばす、`0057`〜`0064` = 所持品）。
- 戦場の狼: 北米版 Commando のコードは日本版と一致しないため、Wiki の日本版のコードを使いました。ROM で、`049C` が残り人数（撃たれると減る）、`04AB` が装備のビット（`20` = 無敵など。ゲーム内で 1 ビットずつ調べている）であることを確かめました。`EB` は面スキップ（`10`）を含みません。
- リンクの冒険（FDS）: 北米版とは RAM の配置が一部違う（体力が北米版 `0774`、日本版 `0770`）ため、日本版向けのコードだけを使っています。

### コードが無いもの（4 本）

| ゲーム | ファイル | 理由 |
|---|---|---|
| さんまの名探偵 | `SANMA.nes` | Wiki のコードは場面ごとに ON / OFF するもの（名前・場所・イベントの進行）で、常に ON にする用途に合わない |
| オホーツクに消ゆ | `Okhotsk ni Kiyu.nes` | コードが見つかりませんでした（アドベンチャーゲーム） |
| ドラえもん | `DRAEMON.nes` | 日本版向けのコードが見つかりませんでした（Wiki はアクセス制限で未確認） |
| リップルアイランド | `LIPURU_ILAND.nes` | コードが見つかりませんでした |

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

## MSX（msx）: 自動で作ったもの

`roms\msx` の 30 本のうち **26 本** のチートを作りました（作成: 2026-09-28、`scripts\msx_cheats.py`）。

MSX のチートは blueMSX の **MCF 形式**（`0,番地,値,0,説明`）です。Retro-Go は、RAM のその番地が読まれたときに値を差し替えます（値が 255 を超えるものは 2 バイト）。出典は、Retro-Go の README が案内している blueMSX の Cheats.zip です（公式サイトは 404 のため archive.org から取得）。

RAM のコードなので、ROM に「書き換え前の値」はありません。代わりに次の方法で、手元の ROM と版が合うかを確かめています。

- **その番地を直接読み書きする Z80 の命令**（`LD A,(nn)` / `LD (nn),A` / `LD HL,nn` など）が ROM にあるかを、番地ごとに調べました。
- ゲームごとに「参照がある番地の割合」を出し、RAM のランダムな番地での割合と比べました。**2 倍以上かつ 30% 以上**（または 3 倍以上かつ 20% 以上）のゲームだけを採用しています。
- 採用したゲームでも、使うのは「直接の参照がある番地」（照合済み）と、「少し手前の番地が参照されている番地」（添字あり: 構造体の中など）だけです。
- 値を固定すると進行が止まるもの（ステージ・面・ミッションの番号）や、座標・色・2P 用のものは除きました。同じ番地で値だけが違うもの（武器の種類など）は、最後の 1 つ（たいてい一番強いもの）だけを残しています。同じ説明で隣り合う 2 バイト（例: 矢の数の下位と上位）は、1 つの 2 バイトのコードにまとめました。

| ゲーム | ファイル | 件数 | 照合済み | 添字あり | 参照の割合 | ランダム時 | 出典のファイル |
|---|---|---|---|---|---|---|---|
| アレスタ | `Aleste (1988)(Compile)(Jp).mcf` | 7 | 6 | 1 | 88% | 4% | aleste1 |
| イー・アル・カンフー | `Yie Ar Kung-Fu (1985)(Konami)[RC-725].mcf` | 2 | 2 | 0 | 100% | 3% | yiearkungfu1 |
| イー・アル・カンフーII | `Yie Ar Kung-Fu II - The Emperor Yie-Gah (1985)(Konami)[a][RC-737].mcf` | 2 | 2 | 0 | 100% | 5% | yiearkungfu2 |
| キングスナイト | `King Knight (1986)(Square)[b].mcf` | 1 | 1 | 0 | 100% | 10% | kingsknight |
| グラディウス | `Nemesis (1986)(Konami)[a][RC-742].mcf` | 15 | 14 | 1 | 95% | 7% | gradius1 |
| グラディウス2 | `Nemesis II (1987)(Konami)[a][RC-751].mcf` | 11 | 11 | 0 | 84% | 11% | gradius2 |
| グーニーズ | `Goonies, The (1986)(Konami)[a][RC-734].mcf` | 8 | 5 | 3 | 70% | 4% | goonies |
| ゴーファーの野望 エピソードII | `Nemesis III - The Eve Of Destruction (1988)(Konami)[a][RC-764].mcf` | 16 | 16 | 0 | 81% | 12% | nemesis3 |
| スターソルジャー | `Star Soldier (1986)(Hudson Soft).mcf` | 2 | 2 | 0 | 100% | 3% | starsoldier |
| スペランカー | `Spelunker (1986)(Irem Corp).mcf` | 5 | 5 | 0 | 100% | 6% | spelunker |
| タンクバタリアン | `Tank Batallion (1980-84)(Namcot).mcf` | 1 | 1 | 0 | 100% | 4% | tankbattalion |
| チャックンポップ | `Chack N Pop (1984)(Taito).mcf` | 3 | 3 | 0 | 31% | 2% | chacknpop |
| ディグダグ | `Dig Dug (1982-84)(Namcot).mcf` | 1 | 1 | 0 | 100% | 5% | digdug |
| ドラゴンスレイヤーIV | `Dragon Slayer 4 - Drasle Family (1987)(Falcom).mcf` | 16 | 13 | 3 | 55% | 3% | dragonslayer4msx2 |
| ドラゴンバスター | `Dragon Buster (1987)(Namcot)[b].mcf` | 2 | 2 | 0 | 80% | 7% | dragonbuster |
| ドルアーガの塔 | `Tower Of Druaga, The (1984-86)(Namcot).mcf` | 4 | 4 | 0 | 100% | 6% | towerofdrauga |
| ハイドライドII | `Hydlide II - Shine Of Darkness (1985)(T&E Soft).mcf` | 5 | 5 | 0 | 100% | 5% | hydlide2 |
| ボルガード | `Volguard (1985)(DB Soft).mcf` | 2 | 2 | 0 | 100% | 2% | volguard |
| メタルギア | `Metal Gear (1987)(Konami)[RC-750].mcf` | 16 | 11 | 5 | 24% | 4% | metalgear1 |
| メタルギア2 ソリッドスネーク | `Metal Gear 2 - Solid Snake (1990)(Konami)[RC-767].mcf` | 16 | 13 | 3 | 52% | 15% | metalgear2 |
| ロマンシア | `Romancia - Dragon Slayer Jr (19xx)(Falcom)[b].mcf` | 6 | 6 | 0 | 100% | 5% | romancia |
| ワープ&ワープ | `Warp & Warp (1980-84)(Namcot).mcf` | 1 | 1 | 0 | 100% | 2% | warpwarp |
| 夢幻戦士ヴァリス | `Valis - The Fantasm Soldier (1987)(Zemina).mcf` | 2 | 2 | 0 | 100% | 5% | fantasmsoldier1 |
| 沙羅曼蛇 | `Salamander (1988)(Zemina)[RC-758].mcf` | 14 | 10 | 4 | 57% | 12% | salamander |
| 魔城伝説 | `MAJYOUDE.mcf` | 8 | 7 | 1 | 67% | 7% | knightmare |
| 魔城伝説II ガリウスの迷宮 | `Knight Mare II - The Maze Of Galious (1987)(Konami)[RC-749].mcf` | 16 | 13 | 3 | 78% | 14% | mazeofgalious |

### コードが無いもの（4 本）

| ゲーム | ファイル | 理由 |
|---|---|---|
| 魔術師麻雀 2 | `Majutsushi Mahjong 2 (1989)(Konami)(Jp)[RC-765].rom` | MCF が見つからなかった |
| 忍者くん | `Ninjakun (1984)(Jaleco)(Jp).rom` | MCF（ninjakun1 / ninjakun2）の番地が、手元の ROM で 1 つも参照されていなかった（版が違う） |
| レリクス | `Relics (19xx)(-)[b].rom` | MCF が見つからなかった |
| トップルジップ | `Topple Zip 2 (1988)(Bothtec).rom` | MCF（topplezipmsx1）の 3 番地のうち 1 つしか参照が無く、版の一致を確かめられなかった |

## 注意

- **チートは Retro-Go の内部フラッシュ（256KB）を使います。** 1 コードあたり、おおよそ「コードと説明の文字数 + 10 バイト」です。いまのチート全体は約 30KB（ファミコン 22KB / PCエンジン 1.4KB / MSX 6.8KB）です。ROM の本数が多いと `region FLASH overflowed` でビルドが失敗します（ROM の一覧も内部フラッシュに入るため）。その場合は、入れる ROM を減らすか、チートのファイルの下の行（優先度の低いもの）を消してください。
- **実機ではまだ試していません。** 「照合済み」でも、ゲームの進行によっては不具合が出ることがあります。おかしくなったら OFF にしてください。
- 1 本あたり最大 16 個です（Retro-Go の上限）。16 個を超える場合は、無敵・残機・体力・時間・武器などを優先し、同じ種類は最大 3 個までにしています。
- **ファミコン / PCエンジンの説明文は日本語です**（2026-09-29 に訳しました。ファイルは UTF-8）。日本語が表示されるのは、③構成のメニュー言語が日本語（CODEPAGE=932）のときだけです。英語（1252）でビルドすると、日本語の説明は外れて、コードがそのまま表示されます。
- 説明文を自分で書き換えるときは、実機の画面幅に収まるよう全角 16 文字くらいまでにしてください。また、「表」「能」「十」「ソ」など、Shift-JIS の 2 バイト目が `\` になる文字は使えません（ビルドで説明が外れ、ログに出ます）。例: 「ソード」→「剣」、「十の位」→「10の位」。
- **MSX の説明文は英語のままです。** Retro-Go が `.mcf` を欧文の文字コード（cp1252）で読むため、日本語にできません。
- 集め直し（`scripts\nes_cheats.py` / `pce_cheats.py`）をしても、日本語にした説明はコードごとに引き継がれます。新しく増えたコードだけが英語になります。
- 使える形式（ファミコン）: ゲームジニー（6 / 8 文字）、`AAAA:VV`（RAM の値を固定）、`AAAA?CC:VV`（比較付き）。1 行に `+` で 3 つまでつなげられます。
- 使える形式（PCエンジン）: `.pceplus` の ROM パッチ。`01822fbd` なら「1 バイト / 番地 $1822F / 値 $BD」です。番地はヘッダ（512 バイト）を除いた位置で、1 行に複数並べられます。
- ファミコン / PCエンジンでは、`#` で始まる行はコメントになりません（メニューに項目として表示されます）。
- 使える形式（MSX）: `.mcf`（`0,番地,値,0,説明`、番地と値は 10 進）。`!` で始まる行はコメントです。1 行に 1 番地で、値が 255 を超えると 2 バイト（下位が先）になります。

## 自分でコードを足す・作り直す

- ファイルを直接編集できます。書式は `コード, 説明` です（1 行 1 項目）。
- ROM を追加したときは、`scripts\nes_cheats.py`（ファミコン）/ `scripts\pce_cheats.py`（PCエンジン）/ `scripts\msx_cheats.py`（MSX）の `MAP` に対応を書き足してから実行すると、作り直せます。

```
tools\venv\Scripts\python.exe scripts\nes_cheats.py
```

- 照合の詳細は `nes\report.json` / `msx\report.json` にあります。

## 出典

- [libretro-database](https://github.com/libretro/libretro-database)（cht/Nintendo - Nintendo Entertainment System）
- [martaaay/game-and-watch-retro-go-game-genie-codes](https://github.com/martaaay/game-and-watch-retro-go-game-genie-codes)
- [ファミコンチート集 Wiki](https://wikiwiki.jp/nnnes1/)（ドラゴンクエスト、ドラえもん、ハイドライド・スペシャル、戦場の狼、サラダの国のトマト姫）
- [olderzeus/game-genie-codes-nes](https://github.com/olderzeus/game-genie-codes-nes)（pceplus フォルダ。PCエンジン）
- [libretro-database](https://github.com/libretro/libretro-database)（cht/Nintendo - Family Computer Disk System。ディスクシステム）
- [blueMSX Cheats.zip](https://web.archive.org/web/2015/http://bluemsx.msxblue.com/rel_download/Cheats.zip)（MCF。MSX。作成: Albert Beevendorp, Patrick van Arkel, Benoît Delvaux）
