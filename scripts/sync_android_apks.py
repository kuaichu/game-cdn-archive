#!/usr/bin/env python3
"""Build static Android APK indexes from known official CDN URLs."""

from __future__ import annotations

import json
import re
import subprocess
import urllib.parse
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept": "*/*",
}


KNOWN_APKS = [
    {
        "game_id": "nte",
        "version": "1.0.2",
        "channel": "official",
        "url": "https://download982100001.wmupd.com/DBBAcAsHETkPNZ/KahEjcXPZw/ZMHiHAAKS/rMETwPrjYHWX/WSsWamksBPBi/xJJBDjteYbWDjH/yGjMzBb/nnaDzeXeMNR/KwmNRJZa.apk",
        "source": "official CDN URL captured manually; versionName read from AndroidManifest.xml",
    },
    {
        "game_id": "reverse1999",
        "version": "1.0.3",
        "channel": "prepage",
        "url": "https://d.bluepoch.com/prepage/Reverse1999_app1.0.3_res100.0.101_Bluepoch_1006.apk",
        "source": "official CDN URL recovered from official historical download page",
        "headers": {"Referer": "https://re.bluepoch.com/"},
    },
    {
        "game_id": "calabiyau",
        "version": "1.1.5.2",
        "channel": "official",
        "url": "https://ms-pack.dl.gxpan.cn/990375/com.idreamsky.klbqm/klbqm_LD0S0N00011.apk",
        "source": "official CDN URL captured manually; versionName read from AndroidManifest.xml",
        "headers": {"Referer": "https://klbq.qq.com/"},
    },
    {
        "game_id": "aethergazer",
        "version": "0.303.501",
        "channel": "303",
        "url": "https://packaging.ys4fun.com/package/channel/303/mimir_ali_prod_303_1_ys4fun_20250910110808_M01000000_LSu3eyVW_sign.apk",
        "source": "official CDN URL recovered from official historical download page; versionName read from AndroidManifest.xml",
        "headers": {"Referer": "https://skzy.ys4fun.com/"},
    },
    {
        "game_id": "aethergazer",
        "version": "0.294.0",
        "channel": "294",
        "url": "https://packaging.ys4fun.com/package/channel/294/mimir_ali_prod_294_1_ys4fun_20240710095639_M01000000_bi3NUfr4_sign.apk",
        "source": "official CDN URL recovered from official historical download page; exact versionName unavailable from remote manifest",
        "headers": {"Referer": "https://skzy.ys4fun.com/"},
    },
    {
        "game_id": "aethergazer",
        "version": "0.285.0",
        "channel": "285",
        "url": "https://download.ys4fun.com/package/channel/285/mimir_ali_prod_285_1_ys4fun_20230522140543_M01000000_jGFY17u6_sign.apk",
        "source": "official CDN URL recovered from official historical download page; exact versionName unavailable from remote manifest",
        "headers": {"Referer": "https://skzy.ys4fun.com/"},
    },
    {
        "game_id": "bluearchive",
        "version": "2.1.2",
        "channel": "Official",
        "url": "https://pkg.bluearchive-cn.com/pubplat/gpp/sdkpackage/prod/game_apk_v2/Official/befa8862e4914729b0344be2892727f5/BlueArchive.apk",
        "source": "official CDN URL captured manually; versionName read from AndroidManifest.xml",
    },
    {
        "game_id": "snowbreak",
        "version": "3.6.0.122",
        "channel": "jinshan",
        "url": "https://cbjq-content.xoyocdn.com/ob202307/setup/ob202307/setup/Android/CBJQ.3.6.0.122.jinshan_202603301341.apk",
        "source": "official CDN URL captured manually; versionName read from AndroidManifest.xml",
    },
    {
        "game_id": "snowbreak",
        "version": "3.5.0.79",
        "channel": "jinshan",
        "url": "https://cbjq-content.xoyocdn.com/ob202307/setup/ob202307/setup/Android/CBJQ.3.5.0.79.jinshan_20260118141532.apk",
        "source": "official CDN URL recovered from official historical download page",
    },
    {
        "game_id": "snowbreak",
        "version": "3.4.0.92",
        "channel": "jinshan",
        "url": "https://cbjq-content.xoyocdn.com/ob202307/setup/ob202307/setup/Android/CBJQ.3.4.0.92.jinshan_20251212164223.apk",
        "source": "official CDN URL recovered from official historical download page",
    },
    {
        "game_id": "snowbreak",
        "version": "3.3.0.82",
        "channel": "jinshan",
        "url": "https://cbjq-content.xoyocdn.com/ob202307/setup/ob202307/setup/Android/CBJQ.3.3.0.82.jinshan.20251029164128.apk",
        "source": "official CDN URL recovered from official historical download page",
    },
    {
        "game_id": "snowbreak",
        "version": "3.2.0.136",
        "channel": "jinshan",
        "url": "https://cbjq-content.xoyocdn.com/ob202307/setup/ob202307/setup/Android/CBJQ.3.2.0.136.jinshan_202509221312.apk",
        "source": "official CDN URL recovered from official historical download page",
    },
    {
        "game_id": "snowbreak",
        "version": "3.0.0",
        "channel": "jinshan",
        "url": "https://cbjq-content.xoyocdn.com/ob202307/setup/ob202307/setup/Android/CBJQ_3.0.0_202507031642_jinshan_30020.mtp.apk",
        "source": "official CDN URL recovered from official historical download page",
    },
    {
        "game_id": "snowbreak",
        "version": "2.5.0.109",
        "channel": "jinshan",
        "url": "https://cbjq-content.xoyocdn.com/ob202307/setup/ob202307/setup/Android/CBJQ.2.5.0.109.jinshan_202501141654.apk",
        "source": "official CDN URL recovered from official historical download page",
    },
    {
        "game_id": "snowbreak",
        "version": "1.8.0.96",
        "channel": "official",
        "url": "https://cbjq-content.xoyocdn.com/ob202307/setup/ob202307/setup/Android/CBJQ.1.8.0.96.202405271642.apk",
        "source": "official CDN URL recovered from official historical download page",
    },
    {
        "game_id": "snowbreak",
        "version": "1.6.0.99",
        "channel": "official",
        "url": "https://cbjq-content.xoyocdn.com/ob202307/setup/ob202307/setup/Android/CBJQ.1.6.0.99_202402281240.apk",
        "source": "official CDN URL recovered from official historical download page",
    },
    {
        "game_id": "wuwa",
        "version": "3.3.2",
        "channel": "官渠",
        "url": "https://mirrors-package-mc.aki-game.com/client/download/20260516183706_FRC8o8CQS9L44Ra4WW/%E9%B8%A3%E6%BD%AE_3.3.2_168377155_33_%E5%AE%98%E6%B8%A0_32e97887831ba8ca620f93b4aa2ad0ff_shelled.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "wuwa",
        "version": "3.0.0",
        "channel": "官渠",
        "url": "https://mirrors-package-mc.aki-game.com/client/download/20251218163511_GpB6itW0p623nE4SMi/%E9%B8%A3%E6%BD%AE_3.0.0_156399220_33_%E5%AE%98%E6%B8%A0_e76c2d8ea383e31af9a8ac20ae3f02e1_shelled.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "wuwa",
        "version": "2.7.0",
        "channel": "官渠",
        "url": "https://mirrors-package-mc.aki-game.com/client/download/20250928105540_sgxqWxKbrnRT8KgK16/%E9%B8%A3%E6%BD%AE_2.7.0_149269354_33_%E5%AE%98%E6%B8%A0_a8cc769870e6ffbad35575179e98b30d_shelled.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "nap",
        "version": "2.8.0",
        "channel": "mktbackup2",
        "url": "https://autopatchcn.juequling.com/package_download/op/client_app/download/20260415151146_HP6JUMY1mL9VnQWt/mktbackup2/ZenlessZoneZero_2.8.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "nap",
        "version": "2.4.0",
        "channel": "gf_1_7",
        "url": "https://autopatchcn.juequling.com/package_download/op/client_app/download/20251107154705_0ujPjXffZwY0voqI/gf_1_7/ZenlessZoneZero_2.4.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "nap",
        "version": "2.3.0",
        "channel": "oonrzywymxk1",
        "url": "https://autopatchcn.juequling.com/package_download/op/client_app/download/20250926175650_zf2LhFSf10NBg5iB/oonrzywymxk1/ZenlessZoneZero_2.3.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "nap",
        "version": "2.0.0",
        "channel": "gw",
        "url": "https://autopatchcn.juequling.com/package_download/op/client_app/download/20250524102650_a8PjvKxdb4vmCkHH/gw/ZenlessZoneZero_2.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "nap",
        "version": "1.3.0",
        "channel": "mktbackup2",
        "url": "https://autopatchcn.juequling.com/package_download/op/client_app/download/20241025155348_P1CiQgR6Uw0z3Pb8/mktbackup2/ZenlessZoneZero_1.3.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "6.6.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20260509191652_EElRT82l302SABA2/mihoyo/yuanshen_6.6.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "6.4.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20260209151532_ootIRmm1n6FxPqzy/mihoyo/yuanshen_6.4.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "6.2.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20251124182449_lRpe1GTcjzBZQBU1/mihoyo/yuanshen_6.2.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "6.1.0",
        "channel": "ydbackup316",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20251013190916_G4Heg91Ag9UeE8Ps/ydbackup316/yuanshen_6.1.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "6.0.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20250901103926_RXhoUrzBjjseDGPk/mihoyo/yuanshen_6.0.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "5.6.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20250427153413_1kLIh8wFZegAqpHw/mihoyo/yuanshen_5.6.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "5.8.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20250718182628_nnOpvKMewCwYMAFU/mihoyo/yuanshen_5.8.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "5.5.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20250314185825_6syHeaRcYTGhEELJ/mihoyo/yuanshen_5.5.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "5.4.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20250125201545_gha0IQ1BkLIOw6B4/mihoyo/yuanshen_5.4.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "5.3.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20241223180529_TD3XG9XKsqN3o88m/mihoyo/yuanshen_5.3.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "5.2.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20241108184319_6NzQMQfgYmRRtnw5/mihoyo/yuanshen_5.2.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "5.0.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20240816175608_Vbb9tDu8AZmKnQKn/mihoyo/yuanshen_5.0.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "4.8.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20240709193922_lKTTQu3hTabVYoWi/mihoyo/yuanshen_4.8.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "4.7.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20240528142546_iDY5Myp8jJv70cF5/mihoyo/yuanshen_4.7.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "4.6.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20240416103648_ZdHhq03TDhSpRocX/mihoyo/yuanshen_4.6.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "4.5.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20240301202146_2eos1Ghjnr2cl6UN/mihoyo/yuanshen_4.5.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "4.2.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20231030114712_nMiBDLnfI0ibjPR1/mihoyo/yuanshen_4.2.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "3.7.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20230513200208_1zoW0Mjbs3RTCNvV/mihoyo/yuanshen_3.7.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "3.6.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20230403105245_M6iuu1yxzEjZAws9/mihoyo/yuanshen_3.6.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "3.5.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20230220115021_vt91MmoiVQHMXe4g/mihoyo/yuanshen_3.5.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "3.4.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20230109151120_vmaeMAkG2koYOJDo/mihoyo/yuanshen_3.4.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "3.2.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20221024105331_bOTAbIxOuQ7A26Yu/mihoyo/yuanshen_3.2.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "3.3.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20221125145552_5ZtiRoenlT70kKdw/mihoyo/yuanshen_3.3.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "3.1.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20220919213200_hkvknSN1UX4opUrq/mihoyo/yuanshen_3.1.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "3.0.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20220815204259_sVvNKoBYqWK1LRwd/mihoyo/yuanshen_3.0.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "2.6.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20220321183336_jY1eJDXeR1hLiFDk/mihoyo/yuanshen_2.6.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "2.1.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/Android/20210901_new_21db95cb081622f9/yuanshen_2.1.0_mihoyo.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "1.6.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/Android/20210609_2758cc87f80c2355/yuanshen_1.6.0_mihoyo.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "1.5.1",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/Android/20210519_5fc626a7d23e64d3/yuanshen_1.5.1_mihoyo.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "1.2.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/Android/20201223_3a5cd05350de467d/yuanshen_1.2.0_mihoyo.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hkrpg",
        "version": "4.3.0",
        "channel": "mihoyo_1",
        "url": "https://autopatchcn.bhsr.com/client/cn/20260523161433_yrgZsgGJ4R1J210J/mihoyo_1/StarRail_4.3.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hkrpg",
        "version": "3.8.0",
        "channel": "gw_An",
        "url": "https://autopatchcn.bhsr.com/client/cn/20251205193454_2JAzO0tkfc1lPb0c/gw_An/StarRail_3.8.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hkrpg",
        "version": "3.7.0",
        "channel": "mihoyo_1",
        "url": "https://autopatchcn.bhsr.com/client/cn/20251025162622_alR6Tz1Le986Lu9q/mihoyo_1/StarRail_3.7.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hkrpg",
        "version": "3.6.0",
        "channel": "gw_An",
        "url": "https://autopatchcn.bhsr.com/client/cn/20250913175807_IPNyJ3QQa0TlG771/gw_An/StarRail_3.6.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hkrpg",
        "version": "3.5.0",
        "channel": "ad_dyst12_An",
        "url": "https://autopatchcn.bhsr.com/client/cn/20250801095521_kFIVD1SzuosxW9vr/ad_dyst12_An/StarRail_3.5.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hkrpg",
        "version": "3.4.0",
        "channel": "gw_An",
        "url": "https://autopatchcn.bhsr.com/client/cn/20250623112713_2bg6PaxrWLL0CPvF/gw_An/StarRail_3.4.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hkrpg",
        "version": "3.1.0",
        "channel": "mihoyo_1",
        "url": "https://autopatchcn.bhsr.com/client/cn/20250214151706_oIzdt9FPrcWYnq4F/mihoyo_1/StarRail_3.1.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hkrpg",
        "version": "1.6.0",
        "channel": "mihoyo_8",
        "url": "https://autopatchcn.bhsr.com/client/cn/20231215090743_ffCg5V2j0gON2tvr/mihoyo_8/StarRail_1.6.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hkrpg",
        "version": "1.3.0",
        "channel": "mihoyo_8",
        "url": "https://autopatchcn.bhsr.com/client/cn/20230818153431_sMKzYZ9EOeT15oNn/StarRail_1.3.0_mihoyo_8.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hkrpg",
        "version": "1.2.0",
        "channel": "mihoyo_8",
        "url": "https://autopatchcn.bhsr.com/client/cn/20230709224719_3CcrEpEKT9iaObJh/StarRail_1.2.0_mihoyo_8.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "bh3",
        "version": "8.9.0",
        "channel": "gw",
        "url": "https://autopatchcn.bh3.com/ptpublic/rel/20260521184041_fIpuozZUX1U7jnuv/CPS/20260514-004049-gf_android_ota-versions-v8_9-Lives_Flourish_gw.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "bh3",
        "version": "7.3.0",
        "channel": "gw",
        "url": "https://bundle.bh3.com/ptpublic/rel/20240129110128_8vnNEN2tuKyZwUhB/CPS/20240125-141104-gf_android_ota-versions-v7_3-Dreamseeking_Voyage_gw.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "bh3",
        "version": "6.6.0",
        "channel": "gw",
        "url": "https://bundle.bh3.com/public/Android/20230413-122623-gf_android_ota-versions-v6_6-Woven_from_Last_Snow_gw.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "bh3",
        "version": "6.5.0",
        "channel": "gw",
        "url": "https://bundle.bh3.com/public/Android/20230301-220508-gf_android_ota-versions-v6_5-Hot_Sands_Escapade_gw.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "bh3",
        "version": "6.4.0",
        "channel": "guofu",
        "url": "https://bundle.bh3.com/public/Android/20230110-030853-gf_android_ota-versions-v6_4-From_Finality_the_Origin_guofu.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "bh3",
        "version": "6.2.0",
        "channel": "guofu",
        "url": "https://bundle.bh3.com/public/Android/20221103-165551-gf_android_ota-versions-v6_2-The_Chrono_and_the_Hare_guofu.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "bh3",
        "version": "6.1.0",
        "channel": "guofu",
        "url": "https://bundle.bh3.com/public/Android/20220922-171040-gf_android_ota-versions-v6_1-Moonshade_Epic_guofu.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "bh3",
        "version": "5.6.0",
        "channel": "guofu",
        "url": "https://bundle.bh3.com/public/Android/20220302-235837-gf_android_ota-versions-v5_6-Elysian_Reverie_guofu.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "bh3",
        "version": "4.3.0",
        "channel": "guofu",
        "url": "https://app.bh3.com/public/Android/20200921-205726-gf_android_ota-versions-v4_3-Rhythms_of_Neon_guofu.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "bh3",
        "version": "3.4.0",
        "channel": "guofu",
        "url": "https://app.bh3.com/public/Android/20190823-210658-gf_android_ota-R3_4-The_Twilight_Ruling_guofu.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "bh3",
        "version": "1.9.0",
        "channel": "guofu",
        "url": "http://app.bh3.com/public/Android/20171123-android_versions_v1_9_resurrection_of_the_sacramental_guofu.apk",
        "source": "Wayback Machine historical URL; original domain no longer resolves",
    },
    {
        "game_id": "bh3",
        "version": "1.8.0",
        "channel": "guofu",
        "url": "http://app.bh3.com/public/Android/20171012-android_versions_v1_8_Scarlet_Mitama_guofu.apk",
        "source": "Wayback Machine historical URL; original domain no longer resolves",
    },
    {
        "game_id": "bh3",
        "version": "1.7.0",
        "channel": "guofu",
        "url": "http://app.bh3.com/public/Android/20170824-android_versions_v1_7_The_Awakening_of_SliverWolf_guofu.apk",
        "source": "Wayback Machine historical URL; original domain no longer resolves",
    },
    {
        "game_id": "bh3",
        "version": "1.6.0",
        "channel": "guofu",
        "url": "http://app.bh3.com/public/Android/20170630-android_versions-v1_6_TogetherinSummer_guofu.apk",
        "source": "Wayback Machine historical URL; original domain no longer resolves",
    },
    {
        "game_id": "bh3",
        "version": "1.5.0",
        "channel": "guofu",
        "url": "http://app.bh3.com/public/Android/20170525-android_versions-v1_5_Theresa_Fight_guofu.apk",
        "source": "Wayback Machine historical URL; original domain no longer resolves",
    },
    {
        "game_id": "bh3",
        "version": "1.4.0",
        "channel": "guofu",
        "url": "http://app.bh3.com/public/Android/20170407-184918-gf_android_ota-versions-v1_4-4R-6d1fb22-ASB-il2cpp_guofu.apk",
        "source": "Wayback Machine historical URL; original domain no longer resolves",
    },
    {
        "game_id": "bh3",
        "version": "1.3.0",
        "channel": "guofu",
        "url": "http://app.bh3.com/public/Android/20170228-202036-gf_android_ota-versions-v1_3_bugfix-updateota-2de1573-ASB-il2cpp_guofu.apk",
        "source": "Wayback Machine historical URL; original domain no longer resolves",
    },
    {
        "game_id": "bh3",
        "version": "1.1.0",
        "channel": "guofu",
        "url": "http://app.bh3.com/public/Android/20161108-112940-gf_android-versions-v1_1-4R-705fcfd-ASB-il2cpp_guofu.apk",
        "source": "Wayback Machine historical URL; original domain no longer resolves",
    },
    {
        "game_id": "bh3",
        "version": "1.0.0",
        "channel": "guofu",
        "url": "http://app.bh3.com/public/Android/0_gf_android-versions-v1_0_2nd-4R-b2b8e16-ASB-mono_guofu.apk",
        "source": "Wayback Machine historical URL; original domain no longer resolves",
    },
]

GAME_NAMES = {
    "nte": {"name": "异环", "subName": "Neverness to Everness"},
    "aethergazer": {"name": "深空之眼", "subName": "Aether Gazer"},
    "arknights": {"name": "明日方舟", "subName": "Arknights"},
    "bluearchive": {"name": "碧蓝档案", "subName": "Blue Archive"},
    "calabiyau": {"name": "卡拉比丘", "subName": "Calabiyau"},
    "endfield": {"name": "明日方舟：终末地", "subName": "Arknights: Endfield"},
    "gf2": {"name": "少女前线2：追放", "subName": "Girls' Frontline 2: Exilium"},
    "pns": {"name": "战双帕弥什", "subName": "Punishing: Gray Raven"},
    "reverse1999": {"name": "重返未来：1999", "subName": "Reverse: 1999"},
    "snowbreak": {"name": "尘白禁区", "subName": "Snowbreak: Containment Zone"},
    "wuwa": {"name": "鸣潮", "subName": "Wuthering Waves"},
    "hk4e": {"name": "原神", "subName": "Genshin Impact"},
    "hkrpg": {"name": "崩坏：星穹铁道", "subName": "Honkai: Star Rail"},
    "nap": {"name": "绝区零", "subName": "Zenless Zone Zero"},
    "bh3": {"name": "崩坏3", "subName": "Honkai Impact 3rd"},
}

DOWNLOAD_PORTER_APIS = [
    {
        "game_id": "hk4e",
        "url": "https://ys-api.mihoyo.com/event/download_porter/link/ys_cn/official/android_default",
    },
    {
        "game_id": "hkrpg",
        "url": "https://api-takumi.mihoyo.com/event/download_porter/link/hkrpg_cn/official/android_default",
    },
    {
        "game_id": "nap",
        "url": "https://api-takumi.mihoyo.com/event/download_porter/link/nap_cn/official/android_default",
    },
    {
        "game_id": "bh3",
        "url": "https://act-api-takumi.mihoyo.com/event/download_porter/link/bh3_cn/bh3/android_gw",
    },
]

NTE_APK_CONFIGS = [
    {
        "game_id": "nte",
        "url": "https://static.games.wanmei.com/public/commonData/gamesData/gameDownload/yh-gameDownload.js",
        "channel": "official",
    },
]

REDIRECT_APK_ENDPOINTS = [
    {
        "game_id": "aethergazer",
        "url": "https://open.ys4fun.com/web-api/pass/linkrouter/gwdl",
        "channel": "gwdl",
        "source": "official Aether Gazer Android download endpoint; resolves to a CDN URL",
        "headers": {"Referer": "https://skzy.ys4fun.com/"},
    },
]

SUNBORN_APK_ENDPOINTS = [
    {
        "game_id": "gf2",
        "url": "https://gf2-web-preregister-api.sunborngame.com/website/url_manage?timestamp=1780775971&nonce=c20j1x&sign=74ca012c6a9ef865f150e6613462bb5a",
        "channel": "gwaz",
        "source": "official Sunborn download API; resolves to a signed APK URL",
    },
]

KURO_APK_INDEXES = [
    {
        "game_id": "pns",
        "url": "https://download.kurogames.com/pns/official/cn/zh-Hans/android_app.json",
        "channel": "官渠",
        "source": "official Punishing: Gray Raven Android download index",
    },
    {
        "game_id": "pns",
        "url": "https://download.kurogames.com/pns/official/cn/zh-Hans/androidpc_app.json",
        "channel": "模拟器",
        "source": "official Punishing: Gray Raven Android emulator download index",
    },
    {
        "game_id": "wuwa",
        "url": "https://download.kurogames.com/mc_WnGtDn85y8lJB4mTmYHYuNjIl9n6YGVm/official/cn/zh-Hans/android_app.json",
        "channel": "官渠",
        "source": "official Wuthering Waves Android download index",
    },
]

HYPERGRYPH_APK_ENDPOINTS = [
    {
        "game_id": "arknights",
        "url": "https://ak.hypergryph.com/downloads/android_lastest",
        "channel": "official",
    },
    {
        "game_id": "endfield",
        "url": "https://launcher.hypergryph.com/game/latest/6LL0KJuqHBVz33WK/1/1",
        "channel": "official",
    },
]


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def normalize_version(version: str) -> str:
    version = version.strip().lstrip("vV")
    parts = [int(part) for part in version.replace("_", ".").split(".") if part != ""]
    while len(parts) < 3:
        parts.append(0)
    return ".".join(str(part) for part in parts[:3])


def version_from_url(url: str) -> str:
    filename = filename_from_url(url)
    patterns = [
        r"yuanshen_(\d+(?:\.\d+){1,2})\.apk$",
        r"StarRail_(\d+(?:\.\d+){1,2})\.apk$",
        r"ZenlessZoneZero_(\d+(?:\.\d+){1,2})\.apk$",
        r"endfield-[^/]*-(\d+(?:\.\d+){1,2})\.apk$",
        r"versions-v(\d+(?:[_\.]\d+){1,2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return normalize_version(match.group(1))
    raise ValueError(f"could not parse APK version from {filename}")


def channel_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path.strip("/")
    parts = path.split("/")
    if len(parts) >= 2:
        return urllib.parse.unquote(parts[-2])
    return "official"


def request_headers(extra_headers: dict | None = None, range_header: str | None = None) -> dict:
    headers = dict(DEFAULT_HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    if range_header:
        headers["Range"] = range_header
    return headers


def curl_header_args(headers: dict) -> list[str]:
    args: list[str] = []
    for key, value in headers.items():
        args.extend(["-H", f"{key}: {value}"])
    return args


def parse_headers(raw_headers: str) -> dict:
    result: dict[str, str | int] = {"status": 0}
    for block in raw_headers.replace("\r\n", "\n").strip().split("\n\n"):
        lines = [line for line in block.split("\n") if line.strip()]
        if not lines or not lines[0].startswith("HTTP/"):
            continue
        status_match = re.search(r"HTTP/\S+\s+(\d+)", lines[0])
        if status_match:
            result = {"status": int(status_match.group(1))}
        for line in lines[1:]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            result[key.strip().lower()] = value.strip()
    return result


def curl_fetch_range(url: str, start: int, end: int, headers: dict | None = None, timeout: int = 60) -> bytes:
    all_headers = request_headers(headers, f"bytes={start}-{end}")
    command = ["curl", "-L", "-s", "--max-time", str(timeout), *curl_header_args(all_headers), url]
    return subprocess.check_output(command)


def curl_head(url: str, headers: dict | None = None, timeout: int = 30) -> dict:
    command = ["curl", "-I", "-L", "-s", "--max-time", str(timeout), *curl_header_args(request_headers(headers)), url]
    raw = subprocess.check_output(command).decode("utf-8", "ignore")
    parsed = parse_headers(raw)
    return {
        "status": int(parsed.get("status") or 0),
        "content_type": str(parsed.get("content-type", "")),
        "size": int(parsed.get("content-length") or 0),
        "last_modified": str(parsed.get("last-modified", "")),
        "etag": str(parsed.get("etag", "")).strip('"'),
        "md5": str(parsed.get("x-cos-meta-md5", "")),
        "crc64": str(parsed.get("x-cos-hash-crc64ecma", "") or parsed.get("x-oss-hash-crc64ecma", "")),
        "error": "",
    }


def curl_content_length(url: str, headers: dict | None = None, timeout: int = 30) -> int:
    command = [
        "curl",
        "-L",
        "-s",
        "-D",
        "-",
        "-o",
        "-",
        "--max-time",
        str(timeout),
        *curl_header_args(request_headers(headers, "bytes=0-0")),
        url,
    ]
    output = subprocess.check_output(command)
    head, _, _ = output.partition(b"\r\n\r\n")
    parsed = parse_headers(head.decode("utf-8", "ignore"))
    content_range = str(parsed.get("content-range", ""))
    if "/" in content_range:
        return int(content_range.rsplit("/", 1)[1])
    return int(parsed.get("content-length") or 0)


def resolve_download_porter_url(
    url: str,
    timeout: int = 30,
    retries: int = 2,
    headers: dict | None = None,
) -> str | None:
    request = urllib.request.Request(url, headers=request_headers(headers))
    for attempt in range(retries + 1):
        try:
            response = urllib.request.urlopen(request, timeout=timeout)
            final_url = response.geturl()
            response.close()
            path = urllib.parse.urlparse(final_url).path.lower()
            return final_url if path.endswith(".apk") else None
        except urllib.error.HTTPError as exc:
            print(f"download porter unavailable {url}: HTTP {exc.code}")
            return None
        except Exception as exc:
            if attempt >= retries:
                print(f"download porter unavailable {url}: {exc}")
    return None


def discover_download_porter_apks() -> list[dict]:
    entries: list[dict] = []
    for item in DOWNLOAD_PORTER_APIS:
        final_url = resolve_download_porter_url(item["url"], headers=item.get("headers"))
        if not final_url:
            continue
        try:
            version = version_from_url(final_url)
        except ValueError as exc:
            print(exc)
            continue
        entries.append({
            "game_id": item["game_id"],
            "version": version,
            "channel": channel_from_url(final_url),
            "url": final_url,
            "source": "official download porter latest endpoint",
            "source_url": item["url"],
        })
    return entries


def fetch_text(url: str, timeout: int = 30, headers: dict | None = None) -> str:
    request = urllib.request.Request(url, headers=request_headers(headers))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "ignore")


def fetch_range(url: str, start: int, end: int, timeout: int = 60, headers: dict | None = None) -> bytes:
    request = urllib.request.Request(
        url,
        headers=request_headers(headers, f"bytes={start}-{end}"),
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" in content_type:
                return curl_fetch_range(url, start, end, headers=headers, timeout=timeout)
            return response.read()
    except Exception:
        return curl_fetch_range(url, start, end, headers=headers, timeout=timeout)


def content_length(url: str, timeout: int = 30, headers: dict | None = None) -> int:
    request = urllib.request.Request(url, headers=request_headers(headers), method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            length = int(response.headers.get("Content-Length") or 0)
            return length or curl_content_length(url, headers=headers, timeout=timeout)
    except urllib.error.HTTPError as exc:
        if exc.code != 405:
            return curl_content_length(url, headers=headers, timeout=timeout)
    except Exception:
        return curl_content_length(url, headers=headers, timeout=timeout)
    range_request = urllib.request.Request(
        url,
        headers=request_headers(headers, "bytes=0-0"),
    )
    try:
        with urllib.request.urlopen(range_request, timeout=timeout) as response:
            content_range = response.headers.get("Content-Range") or ""
            if "/" in content_range:
                return int(content_range.rsplit("/", 1)[1])
            return int(response.headers.get("Content-Length") or 0)
    except Exception:
        return curl_content_length(url, headers=headers, timeout=timeout)


def read_binary_xml_len8(buf: bytes, offset: int) -> tuple[int, int]:
    first = buf[offset]
    offset += 1
    if first & 0x80:
        second = buf[offset]
        offset += 1
        return ((first & 0x7f) << 8) | second, offset
    return first, offset


def read_binary_xml_len16(buf: bytes, offset: int) -> tuple[int, int]:
    first = int.from_bytes(buf[offset:offset + 2], "little")
    offset += 2
    if first & 0x8000:
        second = int.from_bytes(buf[offset:offset + 2], "little")
        offset += 2
        return ((first & 0x7fff) << 16) | second, offset
    return first, offset


def binary_xml_strings(buf: bytes, offset: int) -> tuple[list[str], int]:
    chunk_type = int.from_bytes(buf[offset:offset + 2], "little")
    if chunk_type != 0x0001:
        raise ValueError("AndroidManifest string pool not found")
    header_size = int.from_bytes(buf[offset + 2:offset + 4], "little")
    size = int.from_bytes(buf[offset + 4:offset + 8], "little")
    string_count = int.from_bytes(buf[offset + 8:offset + 12], "little")
    flags = int.from_bytes(buf[offset + 16:offset + 20], "little")
    strings_start = int.from_bytes(buf[offset + 20:offset + 24], "little")
    offsets = [
        int.from_bytes(buf[offset + header_size + index * 4:offset + header_size + index * 4 + 4], "little")
        for index in range(string_count)
    ]
    is_utf8 = bool(flags & 0x100)
    strings_base = offset + strings_start
    strings: list[str] = []
    for relative_offset in offsets:
        cursor = strings_base + relative_offset
        if is_utf8:
            _, cursor = read_binary_xml_len8(buf, cursor)
            byte_length, cursor = read_binary_xml_len8(buf, cursor)
            value = buf[cursor:cursor + byte_length].decode("utf-8", "replace")
        else:
            char_length, cursor = read_binary_xml_len16(buf, cursor)
            value = buf[cursor:cursor + char_length * 2].decode("utf-16le", "replace")
        strings.append(value)
    return strings, offset + size


def binary_manifest_version_name(manifest: bytes) -> str | None:
    if int.from_bytes(manifest[0:2], "little") != 0x0003:
        return None
    strings, offset = binary_xml_strings(manifest, 8)
    while offset < len(manifest):
        chunk_type = int.from_bytes(manifest[offset:offset + 2], "little")
        header_size = int.from_bytes(manifest[offset + 2:offset + 4], "little")
        chunk_size = int.from_bytes(manifest[offset + 4:offset + 8], "little")
        if chunk_type == 0x0102:
            tag_name_index = int.from_bytes(manifest[offset + 20:offset + 24], "little")
            tag_name = strings[tag_name_index] if tag_name_index != 0xffffffff else ""
            attribute_start = int.from_bytes(manifest[offset + 24:offset + 26], "little")
            attribute_size = int.from_bytes(manifest[offset + 26:offset + 28], "little")
            attribute_count = int.from_bytes(manifest[offset + 28:offset + 30], "little")
            attribute_base = offset + header_size + attribute_start
            if tag_name == "manifest":
                for index in range(attribute_count):
                    attribute_offset = attribute_base + index * attribute_size
                    name_index = int.from_bytes(manifest[attribute_offset + 4:attribute_offset + 8], "little")
                    raw_value_index = int.from_bytes(manifest[attribute_offset + 8:attribute_offset + 12], "little")
                    data_type = manifest[attribute_offset + 15]
                    data_value = int.from_bytes(manifest[attribute_offset + 16:attribute_offset + 20], "little")
                    name = strings[name_index] if name_index != 0xffffffff else ""
                    if name != "versionName":
                        continue
                    if raw_value_index != 0xffffffff:
                        return strings[raw_value_index]
                    if data_type == 0x03:
                        return strings[data_value]
                    return str(data_value)
        offset += chunk_size
    return None


def remote_apk_manifest_version_name(url: str, headers: dict | None = None) -> str | None:
    import zlib

    size = content_length(url, headers=headers)
    if not size:
        return None
    tail_size = min(size, 262144)
    tail = fetch_range(url, size - tail_size, size - 1, headers=headers)
    eocd_signature = b"PK\x05\x06"
    eocd_offset = tail.rfind(eocd_signature)
    if eocd_offset < 0:
        return None
    eocd = tail[eocd_offset:eocd_offset + 22]
    central_dir_size = int.from_bytes(eocd[12:16], "little")
    central_dir_offset = int.from_bytes(eocd[16:20], "little")
    central_dir = fetch_range(url, central_dir_offset, central_dir_offset + central_dir_size - 1, headers=headers)
    cursor = 0
    manifest_entry = None
    while cursor < len(central_dir):
        if central_dir[cursor:cursor + 4] != b"PK\x01\x02":
            break
        method = int.from_bytes(central_dir[cursor + 10:cursor + 12], "little")
        compressed_size = int.from_bytes(central_dir[cursor + 20:cursor + 24], "little")
        name_length = int.from_bytes(central_dir[cursor + 28:cursor + 30], "little")
        extra_length = int.from_bytes(central_dir[cursor + 30:cursor + 32], "little")
        comment_length = int.from_bytes(central_dir[cursor + 32:cursor + 34], "little")
        local_offset = int.from_bytes(central_dir[cursor + 42:cursor + 46], "little")
        name = central_dir[cursor + 46:cursor + 46 + name_length].decode("utf-8", "ignore")
        if name == "AndroidManifest.xml":
            manifest_entry = (method, compressed_size, local_offset)
            break
        cursor += 46 + name_length + extra_length + comment_length
    if not manifest_entry:
        return None
    method, compressed_size, local_offset = manifest_entry
    local_header = fetch_range(url, local_offset, local_offset + 30 - 1, headers=headers)
    name_length = int.from_bytes(local_header[26:28], "little")
    extra_length = int.from_bytes(local_header[28:30], "little")
    data_offset = local_offset + 30 + name_length + extra_length
    compressed_manifest = fetch_range(url, data_offset, data_offset + compressed_size - 1, headers=headers)
    if method == 0:
        manifest = compressed_manifest
    elif method == 8:
        manifest = zlib.decompress(compressed_manifest, -15)
    else:
        return None
    return binary_manifest_version_name(manifest)


def discover_nte_apks() -> list[dict]:
    entries: list[dict] = []
    for item in NTE_APK_CONFIGS:
        try:
            text = fetch_text(item["url"]).replace("\\/", "/")
        except Exception as exc:
            print(f"NTE APK config unavailable {item['url']}: {exc}")
            continue
        match = re.search(r'"android"\s*:\s*"([^"]+\.apk)"', text, re.IGNORECASE)
        if not match:
            print(f"NTE APK config has no android APK URL: {item['url']}")
            continue
        apk_url = match.group(1)
        try:
            version = remote_apk_manifest_version_name(apk_url, headers=item.get("headers"))
        except Exception as exc:
            print(f"NTE APK manifest unavailable {apk_url}: {exc}")
            continue
        if not version:
            print(f"NTE APK manifest has no versionName: {apk_url}")
            continue
        entries.append({
            "game_id": item["game_id"],
            "version": version,
            "channel": item["channel"],
            "url": apk_url,
            "source": "official website Android download config; versionName read from AndroidManifest.xml",
            "source_url": item["url"],
        })
    return entries


def discover_redirect_apks() -> list[dict]:
    entries: list[dict] = []
    for item in REDIRECT_APK_ENDPOINTS:
        final_url = resolve_download_porter_url(item["url"], headers=item.get("headers"))
        if not final_url:
            continue
        try:
            version = version_from_url(final_url)
        except ValueError:
            try:
                version = remote_apk_manifest_version_name(final_url, headers=item.get("headers"))
            except Exception as exc:
                print(f"redirect APK manifest unavailable {final_url}: {exc}")
                continue
        if not version:
            print(f"redirect APK has no version: {final_url}")
            continue
        entries.append({
            "game_id": item["game_id"],
            "version": normalize_version(version),
            "channel": item["channel"],
            "url": item["url"],
            "source": item.get("source", "official Android download endpoint; resolves to a CDN URL"),
            "source_url": item["url"],
            "archive_url": final_url,
            "archive_note": "CDN URL captured during sync",
            "metadata_url": final_url,
            "filename_url": final_url,
            "headers": item.get("headers"),
            "force_refresh": True,
        })
    return entries


def discover_sunborn_apks() -> list[dict]:
    entries: list[dict] = []
    for item in SUNBORN_APK_ENDPOINTS:
        try:
            payload = json.loads(fetch_text(item["url"], headers=item.get("headers")))
        except Exception as exc:
            print(f"Sunborn APK API unavailable {item['url']}: {exc}")
            continue
        if payload.get("code") != 0:
            print(f"Sunborn APK API returned code {payload.get('code')}: {item['url']}")
            continue
        apk_url = ""
        for row in payload.get("data", []):
            if row.get("type") == 4 or row.get("Name") == "安卓下载":
                apk_url = row.get("Url") or ""
                break
        if not apk_url:
            print(f"Sunborn APK API has no Android URL: {item['url']}")
            continue
        try:
            version = version_from_url(apk_url)
        except ValueError:
            try:
                version = remote_apk_manifest_version_name(apk_url, headers=item.get("headers"))
            except Exception as exc:
                print(f"Sunborn APK manifest unavailable {apk_url}: {exc}")
                continue
        if not version:
            print(f"Sunborn APK has no version: {apk_url}")
            continue
        entries.append({
            "game_id": item["game_id"],
            "version": normalize_version(version),
            "channel": item["channel"],
            "url": item["url"],
            "source": item.get("source", "official Sunborn download API; resolves to a signed APK URL"),
            "source_url": item["url"],
            "archive_url": apk_url,
            "archive_note": "Signed CDN URL captured during sync",
            "metadata_url": apk_url,
            "filename_url": apk_url,
            "headers": item.get("headers"),
            "force_refresh": True,
        })
    return entries


def discover_kuro_apks() -> list[dict]:
    entries: list[dict] = []
    for item in KURO_APK_INDEXES:
        try:
            index = json.loads(fetch_text(item["url"]))
        except Exception as exc:
            print(f"Kuro APK index unavailable {item['url']}: {exc}")
            continue
        version = index.get("version")
        url = index.get("primary") or index.get("secondary") or index.get("third")
        if not version or not url:
            print(f"Kuro APK index missing version or URL: {item['url']}")
            continue
        entries.append({
            "game_id": item["game_id"],
            "version": normalize_version(version),
            "channel": item["channel"],
            "url": url,
            "source": item.get("source", "official Kuro Android download index"),
            "source_url": item["url"],
        })
    return entries


def discover_hypergryph_apks() -> list[dict]:
    entries: list[dict] = []
    for item in HYPERGRYPH_APK_ENDPOINTS:
        final_url = resolve_download_porter_url(item["url"])
        if not final_url:
            continue
        try:
            version = version_from_url(final_url)
        except ValueError:
            try:
                version = remote_apk_manifest_version_name(final_url, headers=item.get("headers"))
            except Exception as exc:
                print(f"Hypergryph APK manifest unavailable {final_url}: {exc}")
                continue
        if not version:
            print(f"Hypergryph APK has no version: {final_url}")
            continue
        entries.append({
            "game_id": item["game_id"],
            "version": normalize_version(version),
            "channel": item["channel"],
            "url": item["url"],
            "source": "official Hypergryph latest APK endpoint; resolves to a CDN URL",
            "source_url": item["url"],
            "archive_url": final_url,
            "archive_note": "CDN URL captured during sync",
            "metadata_url": final_url,
            "filename_url": final_url,
            "force_refresh": True,
        })
    return entries


def head_url(url: str, headers: dict | None = None) -> dict:
    def range_fallback(meta: dict) -> dict:
        if not url.lower().split("?", 1)[0].endswith(".apk"):
            return meta
        if meta.get("size") and "text/html" not in str(meta.get("content_type", "")).lower():
            return meta
        try:
            probed_size = content_length(url, headers=extra_headers)
        except Exception:
            return meta
        if probed_size > 1024 * 1024:
            return {
                **meta,
                "status": 200,
                "content_type": "application/vnd.android.package-archive",
                "size": probed_size,
                "error": "",
            }
        return {
            **meta,
            "status": 404 if probed_size else int(meta.get("status") or 0),
            "size": 0,
            "error": meta.get("error") or "APK object unavailable",
        }

    extra_headers = headers
    request = urllib.request.Request(url, headers=request_headers(extra_headers), method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response_headers = response.headers
            size = int(response_headers.get("Content-Length") or 0)
            content_type = response_headers.get("Content-Type", "")
            if size == 0 or "text/html" in content_type.lower():
                return range_fallback(curl_head(url, headers=extra_headers, timeout=60))
            return {
                "status": response.status,
                "content_type": content_type,
                "size": size,
                "last_modified": response_headers.get("Last-Modified", ""),
                "etag": (response_headers.get("ETag") or "").strip('"'),
                "md5": response_headers.get("X-Cos-Meta-Md5", ""),
                "crc64": response_headers.get("X-Cos-Hash-Crc64ecma", ""),
                "error": "",
            }
    except Exception as exc:
        try:
            return range_fallback(curl_head(url, headers=extra_headers, timeout=60))
        except Exception:
            return {
                "status": 0,
                "content_type": "",
                "size": 0,
                "last_modified": "",
                "etag": "",
                "md5": "",
                "crc64": "",
                "error": str(exc),
            }


def filename_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path
    return urllib.parse.unquote(Path(path).name)


def md5_from_filename(filename: str) -> str:
    if not filename.endswith(".apk"):
        return ""
    parts = filename.split("_")
    md5_candidates = [
        part
        for part in parts
        if len(part) == 32 and all(ch in "0123456789abcdef" for ch in part.lower())
    ]
    return md5_candidates[-1] if md5_candidates else ""


def apk_hashes(entry: dict) -> set[str]:
    hashes: set[str] = set()
    for value in (entry.get("md5"), md5_from_filename(entry.get("filename") or "")):
        if value and re.fullmatch(r"[0-9a-fA-F]{32}", value):
            hashes.add(value.lower())
    etag = (entry.get("etag") or "").strip().strip('"').lower()
    if etag:
        hashes.add(etag)
        match = re.fullmatch(r"([0-9a-f]{32})(?:-\d+)?", etag)
        if match:
            hashes.add(match.group(1))
    return hashes


def has_same_apk_hash(candidate: dict, entries: list[dict]) -> bool:
    candidate_hashes = apk_hashes(candidate)
    if not candidate_hashes:
        return False
    for entry in entries:
        if entry.get("game_id") != candidate.get("game_id"):
            continue
        if apk_hashes(entry) & candidate_hashes:
            return True
    return False


def same_source_previous(candidate: dict, previous_entries: list[dict]) -> dict | None:
    candidate_hashes = apk_hashes(candidate)
    if not candidate_hashes:
        return None
    for previous in previous_entries:
        if previous.get("game_id") != candidate.get("game_id"):
            continue
        if previous.get("version") != candidate.get("version"):
            continue
        if apk_hashes(previous) & candidate_hashes:
            return previous
    return None


def write_lists(output_dir: Path, game_id: str, version: str, entries: list[dict]) -> dict[str, str]:
    lists_dir = output_dir / "lists"
    lists_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{game_id}_{version}_android"
    urls_path = lists_dir / f"{stem}.urls.txt"
    aria2_path = lists_dir / f"{stem}.aria2.txt"
    json_path = lists_dir / f"{stem}.json"

    urls_path.write_text("\n".join(entry["url"] for entry in entries) + "\n", encoding="utf-8")
    lines: list[str] = []
    for entry in entries:
        lines.append(entry["url"])
        lines.append(f"  dir=Android/{game_id}/{version}")
        lines.append(f"  out={entry['filename']}")
        if entry.get("md5"):
            lines.append(f"  checksum=md5={entry['md5']}")
        lines.append("")
    aria2_path.write_text("\n".join(lines), encoding="utf-8")
    json_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "urls": f"data/android/lists/{urls_path.name}",
        "aria2": f"data/android/lists/{aria2_path.name}",
        "json": f"data/android/lists/{json_path.name}",
    }


def stable_index(index: dict) -> dict:
    stable = json.loads(json.dumps(index, ensure_ascii=False))
    stable.pop("generated_at", None)
    stable.pop("last_checked_at", None)
    for game in stable.get("games", {}).values():
        for entry in game.get("versions", []):
            entry.pop("captured_at", None)
    return stable


def main() -> None:
    output_dir = Path(__file__).resolve().parents[1] / "docs" / "data" / "android"
    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / "index.json"
    previous_index = {}
    if index_path.exists():
        previous_index = json.loads(index_path.read_text(encoding="utf-8"))
    previous_by_url = {
        entry["url"]: entry
        for game in previous_index.get("games", {}).values()
        for entry in game.get("versions", [])
        if entry.get("url")
    }
    previous_by_source_url: dict[str, list[dict]] = {}
    for game in previous_index.get("games", {}).values():
        for entry in game.get("versions", []):
            if entry.get("source_url"):
                previous_by_source_url.setdefault(entry["source_url"], []).append(entry)
    generated_at = datetime.now(timezone.utc).isoformat()
    entries: list[dict] = []

    seeds_by_url = {seed["url"]: seed for seed in KNOWN_APKS}
    for seed in discover_download_porter_apks():
        seeds_by_url.setdefault(seed["url"], seed)
    for seed in discover_nte_apks():
        seeds_by_url.setdefault(seed["url"], seed)
    for seed in discover_redirect_apks():
        seeds_by_url.setdefault(seed["url"], seed)
    for seed in discover_sunborn_apks():
        seeds_by_url.setdefault(seed["url"], seed)
    for seed in discover_kuro_apks():
        seeds_by_url.setdefault(seed["url"], seed)
    for seed in discover_hypergryph_apks():
        seeds_by_url.setdefault(seed["url"], seed)

    for seed in seeds_by_url.values():
        public_seed = {
            key: value
            for key, value in seed.items()
            if key not in {"metadata_url", "filename_url", "force_refresh", "headers"}
        }
        previous = None if seed.get("force_refresh") else previous_by_url.get(seed["url"])
        if previous:
            entry = {**previous, **public_seed}
            filename = entry.get("filename") or filename_from_url(seed["url"])
            entry["filename"] = filename
            entry["md5"] = entry.get("md5") or md5_from_filename(filename)
            entry["captured_at"] = previous.get("captured_at", generated_at)
        else:
            metadata_url = seed.get("metadata_url", seed["url"])
            filename_url = seed.get("filename_url", seed["url"])
            meta = head_url(metadata_url, headers=seed.get("headers"))
            filename = filename_from_url(filename_url)
            entry = {
                **public_seed,
                **meta,
                "md5": meta["md5"] or md5_from_filename(filename),
                "filename": filename,
                "captured_at": generated_at,
            }
        if entry.get("source_url") and not previous and not seed.get("force_refresh"):
            same_source = same_source_previous(entry, previous_by_source_url.get(entry["source_url"], []))
            if same_source:
                entry = {
                    **same_source,
                    "source": seed.get("source", same_source.get("source", "")),
                    "source_url": seed.get("source_url", same_source.get("source_url", "")),
                }
        if entry.get("source_url") and seed.get("force_refresh"):
            same_source = same_source_previous(entry, previous_by_source_url.get(entry["source_url"], []))
            if same_source:
                entry["captured_at"] = same_source.get("captured_at", entry["captured_at"])
                entry["archive_url"] = same_source.get("archive_url") or entry.get("archive_url", "")
                entry["archive_note"] = same_source.get("archive_note") or entry.get("archive_note", "")
        if entry.get("source_url"):
            if has_same_apk_hash(entry, entries):
                print(f"skip duplicate APK hash: {entry['game_id']} {entry['version']} {entry['url']}")
                continue
        entries.append(entry)

    games: dict[str, dict] = {}
    for entry in entries:
        game_id = entry["game_id"]
        game = games.setdefault(game_id, {**GAME_NAMES.get(game_id, {"name": game_id, "subName": game_id}), "versions": []})
        game["versions"].append(entry)

    for game_id, game in games.items():
        game["versions"].sort(key=lambda item: version_key(item["version"]), reverse=True)
        by_version: dict[str, list[dict]] = {}
        for entry in game["versions"]:
            by_version.setdefault(entry["version"], []).append(entry)
        links = {}
        for version, version_entries in by_version.items():
            links[version] = write_lists(output_dir, game_id, version, version_entries)
        game["links"] = links

    index = {
        "last_checked_at": generated_at,
        "generated_at": generated_at,
        "source": "manually captured official Android APK CDN URLs",
        "games": games,
    }
    if previous_index and stable_index(index) == stable_index(previous_index):
        index["generated_at"] = previous_index.get("generated_at", generated_at)

    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote Android APK index for {len(entries)} APKs")


if __name__ == "__main__":
    main()
