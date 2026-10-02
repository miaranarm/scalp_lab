# SCALP LAB V4.11 — ENTRY QUALITY

Trades OOS : 2196
Holdout : exclu

## Global
 trades  mean_net      win  mean_fav6  mean_adv6  be_rate
   2196  -0.00094 0.405282   0.005032  -0.003072 0.535519

## Bougies 1-6
 bars  fav_mean  adv_mean  close_mean  fav_pos  adv_pos
    1  0.001984 -0.000095   -0.000132 0.544627 0.380692
    2  0.001926 -0.000160   -0.000059 0.492714 0.380692
    3  0.002007 -0.000233    0.000005 0.475410 0.372951
    4  0.001899 -0.000237    0.000099 0.470856 0.375683
    5  0.002027 -0.000220    0.000206 0.466758 0.367486
    6  0.002032 -0.000141    0.000103 0.454463 0.359290

## Signal
               signal   n     fav6      adv6       net      win       be
donchian n=50 vol=1.5 323 0.006164 -0.002629 -0.000697 0.393189 0.436533
      pullback rsi=40 416 0.004386 -0.002554 -0.000783 0.401442 0.435096
donchian n=20 vol=0.0 393 0.004867 -0.002814 -0.000801 0.422392 0.679389
        breakout n=20 446 0.006053 -0.003382 -0.000869 0.430493 0.526906
      pullback rsi=35 341 0.003500 -0.002725 -0.000953 0.410557 0.466276
donchian n=20 vol=1.5 133 0.005674 -0.004476 -0.001326 0.330827 0.624060
      vwap n=48 k=3.0 144 0.004191 -0.003749 -0.002154 0.375000 0.763889

## Marché
 symbol interval   n     fav6      adv6       net      win       be
BTCUSDT      15m 539 0.004340 -0.002556 -0.001007 0.393321 0.703154
BTCUSDT       5m 338 0.002129 -0.001356 -0.000539 0.449704 0.298817
ETHUSDT      15m 302 0.007343 -0.003820 -0.000723 0.423841 0.688742
ETHUSDT       5m 364 0.003962 -0.002756 -0.000986 0.337912 0.357143
SOLUSDT      15m 210 0.006559 -0.005094 -0.001964 0.366667 0.704762
SOLUSDT       5m 443 0.004817 -0.002773 -0.000790 0.446953 0.474041

## Entrée originale vs décalée
        mode     fav6      adv6
    original 0.005032 -0.003072
delay_1_open 0.005278 -0.003031
delay_2_open 0.004657 -0.002578

## Méthode
- OOS uniquement.
- V4.4 inchangée.
- OHLC Binance Futures.
- B1 = première bougie suivant l'entrée.
- fav/adv = excursion intrabougie depuis le prix d'entrée.
- delay_1/2 = analyse contrefactuelle, pas nouveau backtest.
- Aucune information future utilisée pour modifier les trades.