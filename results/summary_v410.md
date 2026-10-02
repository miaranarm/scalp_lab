# SCALP LAB V4.10 — ENTRY TIMING FORENSICS

Trades OOS : 2196
Holdout : exclu

## Première direction
first_path    n       net      win      mfe       mae
   ADVERSE 1292 -0.003531 0.191176 0.003166 -0.005932
 FAVORABLE  848  0.002993 0.728774 0.007749 -0.002882
      NONE    1 -0.004313 0.000000 0.005103 -0.005205
  SAME_BAR   55 -0.000663 0.454545 0.006913 -0.005226

## Timing global
 bars  fav  fav_pct  adv  adv_pct  fav_first  adv_first  both
    1  581 0.264572  976 0.444444        493        906    50
    2  736 0.335155 1146 0.521858        610       1045    51
    3  848 0.386157 1251 0.569672        683       1129    53
    4  934 0.425319 1318 0.600182        734       1173    53
    5 1007 0.458561 1362 0.620219        771       1198    54
    6 1063 0.484062 1404 0.639344        797       1220    54

## Signal × timing
               signal  bars   n  fav_first  adv_first  fav_pct  adv_pct
        breakout n=20     1 446        127        177 0.343049 0.448430
        breakout n=20     2 446        146        203 0.396861 0.533632
        breakout n=20     3 446        157        217 0.439462 0.573991
        breakout n=20     4 446        161        228 0.464126 0.605381
        breakout n=20     5 446        169        233 0.506726 0.630045
        breakout n=20     6 446        171        236 0.533632 0.652466
donchian n=20 vol=0.0     1 393         90        162 0.249364 0.424936
donchian n=20 vol=0.0     2 393        112        187 0.325700 0.506361
donchian n=20 vol=0.0     3 393        125        203 0.379135 0.562341
donchian n=20 vol=0.0     4 393        137        212 0.419847 0.603053
donchian n=20 vol=0.0     5 393        144        217 0.450382 0.631043
donchian n=20 vol=0.0     6 393        149        220 0.473282 0.643766
donchian n=20 vol=1.5     1 133         25         66 0.225564 0.518797
donchian n=20 vol=1.5     2 133         32         74 0.293233 0.593985
donchian n=20 vol=1.5     3 133         34         78 0.330827 0.624060
donchian n=20 vol=1.5     4 133         35         82 0.353383 0.661654
donchian n=20 vol=1.5     5 133         36         83 0.375940 0.669173
donchian n=20 vol=1.5     6 133         36         85 0.390977 0.684211
donchian n=50 vol=1.5     1 323         83        139 0.312693 0.492260
donchian n=50 vol=1.5     2 323         98        155 0.380805 0.557276
donchian n=50 vol=1.5     3 323        104        168 0.411765 0.597523
donchian n=50 vol=1.5     4 323        106        172 0.433437 0.616099
donchian n=50 vol=1.5     5 323        109        176 0.455108 0.634675
donchian n=50 vol=1.5     6 323        113        179 0.479876 0.643963
      pullback rsi=35     1 341         82        131 0.281525 0.416422
      pullback rsi=35     2 341        101        153 0.348974 0.486804
      pullback rsi=35     3 341        119        164 0.407625 0.527859
      pullback rsi=35     4 341        129        167 0.451613 0.545455
      pullback rsi=35     5 341        136        173 0.489736 0.568915
      pullback rsi=35     6 341        140        175 0.510264 0.592375
      pullback rsi=40     1 416         56        181 0.158654 0.444712
      pullback rsi=40     2 416         84        215 0.247596 0.531250
      pullback rsi=40     3 416        102        233 0.314904 0.591346
      pullback rsi=40     4 416        116        244 0.377404 0.632212
      pullback rsi=40     5 416        125        247 0.418269 0.646635
      pullback rsi=40     6 416        134        253 0.454327 0.670673
      vwap n=48 k=3.0     1 144         30         50 0.256944 0.375000
      vwap n=48 k=3.0     2 144         37         58 0.326389 0.437500
      vwap n=48 k=3.0     3 144         42         66 0.388889 0.500000
      vwap n=48 k=3.0     4 144         50         68 0.444444 0.520833
      vwap n=48 k=3.0     5 144         52         69 0.458333 0.527778
      vwap n=48 k=3.0     6 144         54         72 0.479167 0.555556

## Marché × timing
 symbol interval  bars   n  fav_first  adv_first  fav_pct  adv_pct
BTCUSDT      15m     1 539        120        239 0.269017 0.476809
BTCUSDT      15m     2 539        142        271 0.346939 0.552876
BTCUSDT      15m     3 539        159        295 0.400742 0.608534
BTCUSDT      15m     4 539        177        301 0.447124 0.628942
BTCUSDT      15m     5 539        185        305 0.474954 0.640074
BTCUSDT      15m     6 539        192        309 0.502783 0.651206
BTCUSDT       5m     1 338         58        133 0.198225 0.408284
BTCUSDT       5m     2 338         77        162 0.266272 0.497041
BTCUSDT       5m     3 338         94        171 0.331361 0.535503
BTCUSDT       5m     4 338        104        178 0.381657 0.568047
BTCUSDT       5m     5 338        113        183 0.428994 0.585799
BTCUSDT       5m     6 338        119        188 0.458580 0.618343
ETHUSDT      15m     1 302         79        101 0.301325 0.380795
ETHUSDT      15m     2 302         99        120 0.380795 0.466887
ETHUSDT      15m     3 302        106        135 0.423841 0.529801
ETHUSDT      15m     4 302        114        146 0.466887 0.572848
ETHUSDT      15m     5 302        119        151 0.496689 0.599338
ETHUSDT      15m     6 302        122        153 0.506623 0.622517
ETHUSDT       5m     1 364         72        184 0.247253 0.543956
ETHUSDT       5m     2 364         88        209 0.302198 0.615385
ETHUSDT       5m     3 364         99        221 0.343407 0.651099
ETHUSDT       5m     4 364        102        228 0.373626 0.678571
ETHUSDT       5m     5 364        105        232 0.398352 0.695055
ETHUSDT       5m     6 364        108        234 0.423077 0.706044
SOLUSDT      15m     1 210         37         89 0.209524 0.457143
SOLUSDT      15m     2 210         49        103 0.276190 0.528571
SOLUSDT      15m     3 210         57        109 0.333333 0.561905
SOLUSDT      15m     4 210         61        114 0.361905 0.600000
SOLUSDT      15m     5 210         62        116 0.380952 0.619048
SOLUSDT      15m     6 210         65        120 0.414286 0.642857
SOLUSDT       5m     1 443        127        160 0.325056 0.388262
SOLUSDT       5m     2 443        155        180 0.397291 0.460497
SOLUSDT       5m     3 443        168        198 0.444695 0.512415
SOLUSDT       5m     4 443        176        206 0.476298 0.544018
SOLUSDT       5m     5 443        187        211 0.521445 0.575621
SOLUSDT       5m     6 443        191        216 0.548533 0.595937

## Méthode
- Analyse OOS uniquement.
- Aucun signal ni paramètre modifié.
- Horizon : 1 à 6 bougies après l'entrée.
- TP50/SL50 servent uniquement à identifier la première direction.
- Une même bougie peut toucher les deux niveaux : ordre intrabougie inconnu.