# JTE data directory

**2026-08-05 formula release.** Jungle (vision counts removed: they are
personal habits, not performance — see `docs/BENCHMARKS.md` B6), Top
(`TDPG_share_oe`: tower share scored against expectation given teammates'
output, pooled frozen slopes in `engine/_OE_baselines.json` — refit with
`py tools/fit_oe_baselines.py` after every data refresh, BEFORE the master
build), Middle (KS_pct deleted: champion pool). `DMG_DTH_ratio` published as
a standalone statistic. Event CSVs regenerated on the same engine.

Provenance and rebuild notes for every CSV in this folder. All data originates
from the newmodel OE refresh pipeline (`newmodel/oe_refresh/`, daily refresh;
this copy covers games through **2026-08-05**).

Refresh with `py tools/refresh_data.py <raw OE csv>`. That runs newmodel's own
`filter_per_game.py` -- so the league whitelist, the LVP SL -> LES rename and
the promo-bracket exclusions match the prediction pipeline exactly -- and then
applies the exclusions that are specific to the index.

**KeSPA Cup is excluded from the index.** newmodel maps `KeSPA Cup` -> `LCK`,
which is correct for prediction (same organisations, informs team strength) and
wrong for CAR. CAR is league-relative: z-scores and the replacement baseline are
computed inside a (league, year) pool, so folding a short academy-heavy cup into
the LCK season merges two competitions into one cohort. When the 43 cup games
were included, a 6-game substitute support rated +78.9 -- above Chovy -- and
Chovy moved 72.4 -> 58.9 purely because the pool he is measured against changed.
If the cup is ever wanted on the site it should arrive as its own cohort, not
merged into the season.

| File | What it is | Source |
|---|---|---|
| `msi2026_per_game.csv` | Full filtered per-game rows (player + team) for MSI 2026: 71 games, 11 teams, 2026-06-28 to 2026-07-12. Complete timeline coverage. | Raw all-leagues OE drop, `league == "MSI"` |
| `msi2026_players.csv` | Per-player MSI-only ratings from the LIVE CAR engine using the deployed role formulas (`engine/rebuild_weights.json`): CAR, CPS composite, radar axes (JSON column `radar_axes`), role rank. The engine z-scores components and sets replacement within the slice it is handed, so passing it MSI games alone gives event-only ratings with no domestic carryover. Champion neutralization OFF (71 games is too thin to estimate effects from). | Built by `tools/build_event_dataset.py` |
| `oe_2026_per_game_filtered.csv` | The canonical domestic refresh artifact (CAR league set: LCK, LEC, LCS, LCP, CBLOL + development leagues). MSI / LPL / EWC are deliberately excluded by the refresh filter. | `newmodel/oe_refresh/per_game/2026_per_game_filtered.csv` |
| `lpl_per_game.csv` | The LPL substrate, 2023-2026, full OE schema. OE's own LPL rows have no timeline data; the 2026 team rows carry a `golddiffat25` backfill from the tabesports.gg gold curves. Player-level timeline diffs (GD10/XPD10 etc.) remain null, which limits which CAR components LPL can support. | `newmodel/lpl_data/lpl_per_game.csv` |

| `msi2026_isolated_deaths.csv` | Coordinate-based discipline ledger: isolated, uncompensated side-lane deaths past 20:00 (and picks secured), from the tabesports events substrate (68/71 MSI games carry coordinates). | Built by `tools/coord_isolated_deaths.py` |

## Rebuilding the event dataset

```
py tools/build_event_dataset.py --league MSI --year 2026 \
    --source "C:/Users/jaspe/AppData/Local/Temp/oe_extract/2026_LoL_esports_match_data_from_OraclesElixir.csv" \
    --out-prefix msi2026
```

The same tool builds any future event edition (Worlds, EWC) by switching
`--league` / `--year` / `--out-prefix`. The landing-page dissection reads
`msi2026_players.csv` directly via PapaParse.
