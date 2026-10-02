# SCALP LAB V4.9 — PATH × EDGE FORENSICS

- Trades OOS : 2196
- FINAL HOLDOUT : exclu
- Source : V4.8 trade paths
- Stratégie V4.4 : inchangée
- Aucun nouveau paramètre testé.

## Global

- mean net/trade : -0.094%
- median net : -0.281%
- win rate : 40.53%
- mean MFE : 0.503%
- mean MAE : -0.474%
- TP50 avant SL50 : 848 (38.62%)
- SL50 avant TP50 : 1292 (58.83%)

## Path classes

     path_class  trades  mean_net  median_net  win_rate  mean_mfe  mean_mae  mean_duration  tp  sl  time  tp50_first  sl50_first
 AMBIGUOUS_PATH      55 -0.000663   -0.002047  0.454545  0.006913 -0.005226       4.290909  24  29     2           0           0
  EARLY_ADVERSE    1292 -0.003531   -0.004089  0.191176  0.003166 -0.005932       8.698916 195 991   106           0        1292
EARLY_FAVORABLE     184 -0.003234   -0.003903  0.266304  0.005051 -0.005980      14.342391  27 120    37         184           0
 FAVORABLE_PATH     664  0.004719    0.004604  0.856928  0.008496 -0.002023       8.652108 545  73    46         664           0
       NO_TOUCH       1 -0.004313   -0.004313  0.000000  0.005103 -0.005205      24.000000   0   0     1           0           0

## Exit × Path

exit_reason      path_class  trades  mean_net  median_net  win_rate  mean_mfe  mean_mae  mean_duration  tp  sl  time  tp50_first  sl50_first
         SL  AMBIGUOUS_PATH      29 -0.005583   -0.005404  0.000000  0.005544 -0.007423       2.827586   0  29     0           0           0
         SL   EARLY_ADVERSE     991 -0.005724   -0.005002  0.000000  0.001794 -0.006488       6.332997   0 991     0           0         991
         SL EARLY_FAVORABLE     120 -0.006155   -0.005390  0.000000  0.004246 -0.007125      10.650000   0 120     0         120           0
         SL  FAVORABLE_PATH      73 -0.005582   -0.005199  0.000000  0.005569 -0.006208      14.054795   0  73     0          73           0
       TIME  AMBIGUOUS_PATH       2 -0.000095   -0.000095  0.500000  0.003122 -0.002268      18.000000   0   0     2           0           0
       TIME   EARLY_ADVERSE     106 -0.000632   -0.000147  0.490566  0.005656 -0.005568      27.169811   0   0   106           0         106
       TIME EARLY_FAVORABLE      37 -0.000492    0.000293  0.594595  0.005221 -0.003945      25.945946   0   0    37          37           0
       TIME  FAVORABLE_PATH      46 -0.000149    0.000130  0.521739  0.006465 -0.002966      26.608696   0   0    46          46           0
       TIME        NO_TOUCH       1 -0.004313   -0.004313  0.000000  0.005103 -0.005205      24.000000   0   0     1           0           0
         TP  AMBIGUOUS_PATH      24  0.005235    0.003878  1.000000  0.008883 -0.002818       4.916667  24   0     0           0           0
         TP   EARLY_ADVERSE     195  0.006039    0.005029  1.000000  0.008785 -0.003306      10.682051 195   0     0           0         195
         TP EARLY_FAVORABLE      27  0.005992    0.005384  1.000000  0.008391 -0.003680      14.851852  27   0     0          27           0
         TP  FAVORABLE_PATH     545  0.006509    0.005350  1.000000  0.009060 -0.001383       6.412844 545   0     0         545           0

## Signal × Path

               signal      path_class  trades  mean_net  median_net  win_rate  mean_mfe  mean_mae  mean_duration  tp  sl  time  tp50_first  sl50_first
        breakout n=20  AMBIGUOUS_PATH      17  0.002053    0.003151  0.588235  0.008593 -0.003993       2.823529  10   7     0           0           0
        breakout n=20   EARLY_ADVERSE     251 -0.003719   -0.004918  0.227092  0.003905 -0.006823       8.892430  50 182    19           0         251
        breakout n=20 EARLY_FAVORABLE      39 -0.003988   -0.003912  0.230769  0.006042 -0.006742      12.641026   6  23    10          39           0
        breakout n=20  FAVORABLE_PATH     138  0.004861    0.005024  0.840580  0.009425 -0.002546       7.275362 113  17     8         138           0
        breakout n=20        NO_TOUCH       1 -0.004313   -0.004313  0.000000  0.005103 -0.005205      24.000000   0   0     1           0           0
donchian n=20 vol=0.0  AMBIGUOUS_PATH       5 -0.000631    0.003351  0.600000  0.008245 -0.009580       5.000000   3   2     0           0           0
donchian n=20 vol=0.0   EARLY_ADVERSE     231 -0.003714   -0.004622  0.199134  0.003427 -0.006161       9.437229  35 173    23           0         231
donchian n=20 vol=0.0 EARLY_FAVORABLE      35 -0.003571   -0.004758  0.257143  0.005868 -0.007287      14.371429   7  25     3          35           0
donchian n=20 vol=0.0  FAVORABLE_PATH     122  0.005501    0.004748  0.885246  0.009571 -0.002089       8.811475 100  12    10         122           0
donchian n=20 vol=1.5  AMBIGUOUS_PATH       3 -0.004474   -0.007467  0.333333  0.010001 -0.006488       1.000000   1   2     0           0           0
donchian n=20 vol=1.5   EARLY_ADVERSE      91 -0.003822   -0.004787  0.164835  0.003725 -0.006682       7.945055  13  75     3           0          91
donchian n=20 vol=1.5 EARLY_FAVORABLE       7 -0.005560   -0.007599  0.142857  0.007928 -0.009292      13.714286   1   6     0           7           0
donchian n=20 vol=1.5  FAVORABLE_PATH      32  0.006995    0.006173  0.843750  0.012697 -0.001929       6.593750  27   4     1          32           0
donchian n=50 vol=1.5  AMBIGUOUS_PATH      17 -0.003151   -0.003351  0.294118  0.005655 -0.005975       4.352941   5  12     0           0           0
donchian n=50 vol=1.5   EARLY_ADVERSE     188 -0.004023   -0.004626  0.132979  0.003053 -0.005869       8.143617  22 156    10           0         188
donchian n=50 vol=1.5 EARLY_FAVORABLE      15 -0.001555   -0.003705  0.333333  0.006504 -0.004895      14.933333   3  10     2          15           0
donchian n=50 vol=1.5  FAVORABLE_PATH     103  0.005905    0.006130  0.893204  0.009787 -0.001765       7.087379  89   8     6         103           0
      pullback rsi=35  AMBIGUOUS_PATH       6 -0.001594   -0.001824  0.333333  0.002984 -0.004102       6.166667   1   4     1           0           0
      pullback rsi=35   EARLY_ADVERSE     187 -0.003106   -0.003271  0.171123  0.002068 -0.004866       7.834225  23 148    16           0         187
      pullback rsi=35 EARLY_FAVORABLE      29 -0.002654   -0.003079  0.206897  0.003291 -0.005006      13.517241   4  21     4          29           0
      pullback rsi=35  FAVORABLE_PATH     119  0.002876    0.003040  0.840336  0.006077 -0.001943      10.033613  96  13    10         119           0
      pullback rsi=40  AMBIGUOUS_PATH       4  0.005406    0.004977  1.000000  0.007176 -0.002072       3.750000   4   0     0           0           0
      pullback rsi=40   EARLY_ADVERSE     262 -0.002598   -0.003119  0.217557  0.002732 -0.004860       9.087786  43 195    24           0         262
      pullback rsi=40 EARLY_FAVORABLE      38 -0.002674   -0.003029  0.315789  0.003941 -0.004553      15.026316   5  24     9          38           0
      pullback rsi=40  FAVORABLE_PATH     112  0.003881    0.003354  0.839286  0.006738 -0.001681      10.723214  88  15     9         112           0
      vwap n=48 k=3.0  AMBIGUOUS_PATH       3 -0.004424   -0.005441  0.000000  0.006724 -0.005904      11.333333   0   2     1           0           0
      vwap n=48 k=3.0   EARLY_ADVERSE      82 -0.004944   -0.005902  0.182927  0.003694 -0.007728       8.865854   9  62    11           0          82
      vwap n=48 k=3.0 EARLY_FAVORABLE      21 -0.003510   -0.005131  0.333333  0.004287 -0.005986      17.142857   1  11     9          21           0
      vwap n=48 k=3.0  FAVORABLE_PATH      38  0.004795    0.005073  0.842105  0.007395 -0.001946       8.684211  32   4     2          38           0

## Market × Path

 symbol interval      path_class  trades  mean_net  median_net  win_rate  mean_mfe  mean_mae  mean_duration  tp  sl  time  tp50_first  sl50_first
BTCUSDT      15m  AMBIGUOUS_PATH      15  0.000054    0.001874  0.533333  0.006532 -0.005515       4.200000   8   6     1           0           0
BTCUSDT      15m   EARLY_ADVERSE     322 -0.003247   -0.004128  0.195652  0.002841 -0.005406       8.695652  49 238    35           0         322
BTCUSDT      15m EARLY_FAVORABLE      41 -0.002489   -0.003958  0.292683  0.004778 -0.005220      15.048780   5  28     8          41           0
BTCUSDT      15m  FAVORABLE_PATH     161  0.003753    0.004559  0.801242  0.007373 -0.001898       8.869565 122  25    14         161           0
BTCUSDT       5m  AMBIGUOUS_PATH       5  0.000749    0.001856  0.600000  0.002997 -0.001940       6.800000   2   2     1           0           0
BTCUSDT       5m   EARLY_ADVERSE     199 -0.002040   -0.002779  0.221106  0.001639 -0.003363       9.587940  31 146    22           0         199
BTCUSDT       5m EARLY_FAVORABLE      29 -0.001955   -0.002541  0.310345  0.002598 -0.002966      17.034483   3  19     7          29           0
BTCUSDT       5m  FAVORABLE_PATH     105  0.002634    0.002747  0.914286  0.004425 -0.001123      10.638095  91   6     8         105           0
ETHUSDT      15m  AMBIGUOUS_PATH       9 -0.005467   -0.006687  0.111111  0.009607 -0.011827       2.777778   1   8     0           0           0
ETHUSDT      15m   EARLY_ADVERSE     166 -0.004868   -0.006394  0.192771  0.005466 -0.008861      10.331325  25 124    17           0         166
ETHUSDT      15m EARLY_FAVORABLE      36 -0.004162   -0.005475  0.305556  0.008325 -0.009128      14.222222   8  21     7          36           0
ETHUSDT      15m  FAVORABLE_PATH      91  0.008669    0.008217  0.923077  0.014385 -0.002995       7.637363  82   5     4          91           0
ETHUSDT       5m  AMBIGUOUS_PATH      10  0.000178   -0.000015  0.500000  0.004841 -0.001966       6.000000   5   5     0           0           0
ETHUSDT       5m   EARLY_ADVERSE     241 -0.003091   -0.003486  0.136929  0.002044 -0.004371       7.062241  29 206     6           0         241
ETHUSDT       5m EARLY_FAVORABLE      18 -0.001926   -0.003272  0.222222  0.003474 -0.003440      12.277778   3  13     2          18           0
ETHUSDT       5m  FAVORABLE_PATH      95  0.004407    0.004436  0.852632  0.008124 -0.001471       8.484211  78  11     6          95           0
SOLUSDT      15m  AMBIGUOUS_PATH       5 -0.002943   -0.006304  0.400000  0.007543 -0.006073       1.800000   2   3     0           0           0
SOLUSDT      15m   EARLY_ADVERSE     135 -0.005290   -0.007190  0.192593  0.005625 -0.010101       8.600000  21 105     9           0         135
SOLUSDT      15m EARLY_FAVORABLE      17 -0.006682   -0.007599  0.176471  0.006949 -0.010534      12.411765   1  13     3          17           0
SOLUSDT      15m  FAVORABLE_PATH      53  0.008112    0.009081  0.867925  0.013807 -0.003347       8.830189  43   5     5          53           0
SOLUSDT       5m  AMBIGUOUS_PATH      11  0.001922    0.003351  0.545455  0.008605 -0.003503       4.090909   6   5     0           0           0
SOLUSDT       5m   EARLY_ADVERSE     229 -0.003683   -0.004859  0.213974  0.003013 -0.005966       8.528384  40 172    17           0         229
SOLUSDT       5m EARLY_FAVORABLE      43 -0.003214   -0.004306  0.232558  0.004132 -0.005366      13.581395   7  26    10          43           0
SOLUSDT       5m  FAVORABLE_PATH     159  0.003866    0.004391  0.836478  0.007405 -0.002076       7.742138 129  21     9         159           0
SOLUSDT       5m        NO_TOUCH       1 -0.004313   -0.004313  0.000000  0.005103 -0.005205      24.000000   0   0     1           0           0

## Regime × Path

regime      path_class  trades  mean_net  median_net  win_rate  mean_mfe  mean_mae  mean_duration  tp  sl  time  tp50_first  sl50_first
   all  AMBIGUOUS_PATH       6 -0.000214    0.000101  0.500000  0.003983 -0.003657       6.000000   2   3     1           0           0
   all   EARLY_ADVERSE     211 -0.003202   -0.003373  0.194313  0.002990 -0.006028       7.028436  31 165    15           0         211
   all EARLY_FAVORABLE      28 -0.003676   -0.003348  0.214286  0.004319 -0.006083      12.250000   3  20     5          28           0
   all  FAVORABLE_PATH     101  0.004121    0.004756  0.801980  0.008242 -0.002478       9.326733  77  17     7         101           0
 range  AMBIGUOUS_PATH      35 -0.000970   -0.002300  0.428571  0.006493 -0.004237       3.771429  15  20     0           0           0
 range   EARLY_ADVERSE     601 -0.003750   -0.004573  0.169717  0.003436 -0.006007       8.131448  86 487    28           0         601
 range EARLY_FAVORABLE      71 -0.003082   -0.003723  0.239437  0.005320 -0.005374      13.802817  10  48    13          71           0
 range  FAVORABLE_PATH     260  0.005693    0.005256  0.861538  0.009974 -0.001839       7.765385 216  29    15         260           0
 trend  AMBIGUOUS_PATH      14 -0.000088    0.000345  0.500000  0.009219 -0.008370       4.857143   7   6     1           0           0
 trend   EARLY_ADVERSE     480 -0.003401   -0.004051  0.216667  0.002904 -0.005796      10.143750  78 339    63           0         480
 trend EARLY_FAVORABLE      85 -0.003216   -0.004063  0.305882  0.005066 -0.006453      15.482353  14  52    19          85           0
 trend  FAVORABLE_PATH     303  0.004082    0.004239  0.871287  0.007313 -0.002030       9.188119 252  27    24         303           0
 trend        NO_TOUCH       1 -0.004313   -0.004313  0.000000  0.005103 -0.005205      24.000000   0   0     1           0           0

## Edge classes

         edge_class  trades  mean_net  median_net  win_rate  mean_mfe  mean_mae  mean_duration  tp  sl  time  tp50_first  sl50_first
 EARLY_ADVERSE_LOSS    1045 -0.005618   -0.004879   0.00000  0.001923 -0.006472       7.349282   0 991    54           0        1045
  EARLY_ADVERSE_WIN     247  0.005296    0.004151   1.00000  0.008424 -0.003648      14.408907 195   0    52           0         247
EARLY_FAVORABLE_WIN      49  0.003904    0.003047   1.00000  0.006869 -0.003522      20.183673  27   0    22          49           0
     FAVORABLE_LOSS      95 -0.004852   -0.004373   0.00000  0.005783 -0.005651      16.989474   0  73    22          95           0
      FAVORABLE_WIN     569  0.006316    0.005234   1.00000  0.008949 -0.001417       7.260105 545   0    24         569           0
              OTHER     191 -0.004330   -0.004325   0.13089  0.005120 -0.006390      10.000000  24 149    18         135           0

## Méthode

- Analyse strictement OOS.
- FINAL HOLDOUT exclu.
- Aucun recalcul de signal.
- Aucun paramètre modifié.
- Aucune nouvelle stratégie testée.
- Les trajectoires viennent de V4.8.
- L'objectif est d'isoler la source de l'edge et des pertes.