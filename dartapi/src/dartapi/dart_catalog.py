# -*- coding:utf-8 -*-
# Return field catalogs for DART OpenAPI endpoints.
# Each entry: {"description": str, "fields": {field_name: description}}

from typing import Dict

_FieldMap = Dict[str, str]

# ----- Common Return Fields ----- #
# Fields shared across (almost) every DART OpenAPI JSON endpoint. Individual
# endpoints either spread these verbatim (`**COMMON_RETURN_FIELDS`) or override a
# single entry (e.g. report uses 법인명 for corp_name, share drops corp_cls).
COMMON_RETURN_FIELDS: _FieldMap = {
    "rcept_no": "접수번호(14자리). 공시뷰어 접근 시 사용",
    "corp_cls": "법인구분 (Y:유가, K:코스닥, N:코넥스, E:기타)",
    "corp_code": "고유번호 (공시대상회사의 고유번호 8자리)",
    "corp_name": "회사명 (공시대상회사명)",
}

# ----- Event Catalogue (주요사항보고서 주요정보) ----- #
# source: https://opendart.fss.or.kr/guide/main.do?apiGrpCd=DS005

# event/regstate use the common fields as-is.
_COMMON_EVENT_FIELDS: _FieldMap = COMMON_RETURN_FIELDS

_COMMON_BOARD_FIELDS: _FieldMap = {
    "bddd": "이사회결의일(결정일)",
    "od_a_at_t": "사외이사 참석여부(참석(명))",
    "od_a_at_b": "사외이사 참석여부(불참(명))",
    "adt_a_atn": "감사(감사위원) 참석여부",
}

_COMMON_BOND_FIELDS: _FieldMap = {
    "bd_tm": "사채의 종류(회차)",
    "bd_knd": "사채의 종류(종류)",
    "bd_fta": "사채의 권면(전자등록)총액 (원)",
    "ovis_fta": "해외발행(권면(전자등록)총액)",
    "ovis_fta_crn": "해외발행(권면(전자등록)총액(통화단위))",
    "ovis_ster": "해외발행(기준환율등)",
    "ovis_isar": "해외발행(발행지역)",
    "ovis_mktnm": "해외발행(해외상장시 시장의 명칭)",
    "fdpp_fclt": "자금조달의 목적(시설자금 (원))",
    "fdpp_bsninh": "자금조달의 목적(영업양수자금 (원))",
    "fdpp_op": "자금조달의 목적(운영자금 (원))",
    "fdpp_dtrp": "자금조달의 목적(채무상환자금 (원))",
    "fdpp_ocsa": "자금조달의 목적(타법인 증권 취득자금 (원))",
    "fdpp_etc": "자금조달의 목적(기타자금 (원))",
    "bd_intr_ex": "사채의 이율(표면이자율 (%))",
    "bd_intr_sf": "사채의 이율(만기이자율 (%))",
    "bd_mtd": "사채만기일",
    "bdis_mthn": "사채발행방법",
    "sbd": "청약일",
    "pymd": "납입일",
    "rpmcmp": "대표주관회사",
    "grint": "보증기관",
    "rs_sm_atn": "증권신고서 제출대상 여부",
    "ex_sm_r": "제출을 면제받은 경우 그 사유",
    "ovis_ltdtl": "당해 사채의 해외발행과 연계된 대차거래 내역",
    "ftc_stt_atn": "공정거래위원회 신고대상 여부",
}


EVENT_RETURN_FIELDS_CATALOG: Dict[str, Dict] = {
    "astInhtrfEtcPtbkOpt": {
        "description": "자산양수도(기타), 풋백옵션",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "rp_rsn": "보고 사유",
            "ast_inhtrf_prc": "자산양수ㆍ도 가액",
        },
    },
    "dfOcr": {
        "description": "부도발생",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "df_cn": "부도내용",
            "df_amt": "부도금액",
            "df_bnk": "부도발생은행",
            "dfd": "최종부도(당좌거래정지)일자",
            "df_rs": "부도사유 및 경위",
        },
    },
    "bsnSp": {
        "description": "영업정지",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "bsnsp_rm": "영업정지 분야",
            "bsnsp_amt": "영업정지 내역(영업정지금액)",
            "rsl": "영업정지 내역(최근매출총액)",
            "sl_vs": "영업정지 내역(매출액 대비)",
            "ls_atn": "영업정지 내역(대규모법인여부)",
            "krx_stt_atn": "영업정지 내역(거래소 의무공시 해당 여부)",
            "bsnsp_cn": "영업정지 내용",
            "bsnsp_rs": "영업정지사유",
            "ft_ctp": "향후대책",
            "bsnsp_af": "영업정지영향",
            "bsnspd": "영업정지일자",
            **_COMMON_BOARD_FIELDS,
        },
    },
    "ctrcvsBgrq": {
        "description": "회생절차 개시신청",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "apcnt": "신청인 (회사와의 관계)",
            "cpct": "관할법원",
            "rq_rs": "신청사유",
            "rqd": "신청일자",
            "ft_ctp_sc": "향후대책 및 일정",
        },
    },
    "dsRsOcr": {
        "description": "해산사유 발생",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "ds_rs": "해산사유",
            "ds_rsd": "해산사유발생일(결정일)",
            **_COMMON_BOARD_FIELDS,
        },
    },
    "piicDecsn": {
        "description": "유상증자 결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "nstk_ostk_cnt": "신주의 종류와 수(보통주식 (주))",
            "nstk_estk_cnt": "신주의 종류와 수(기타주식 (주))",
            "fv_ps": "1주당 액면가액 (원)",
            "bfic_tisstk_ostk": "증자전 발행주식총수 (주)(보통주식 (주))",
            "bfic_tisstk_estk": "증자전 발행주식총수 (주)(기타주식 (주))",
            "fdpp_fclt": "자금조달의 목적(시설자금 (원))",
            "fdpp_bsninh": "자금조달의 목적(영업양수자금 (원))",
            "fdpp_op": "자금조달의 목적(운영자금 (원))",
            "fdpp_dtrp": "자금조달의 목적(채무상환자금 (원))",
            "fdpp_ocsa": "자금조달의 목적(타법인 증권 취득자금 (원))",
            "fdpp_etc": "자금조달의 목적(기타자금 (원))",
            "ic_mthn": "증자방식",
            "ssl_at": "공매도 해당여부",
            "ssl_bgd": "공매도 시작일",
            "ssl_edd": "공매도 종료일",
        },
    },
    "fricDecsn": {
        "description": "무상증자 결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "nstk_ostk_cnt": "신주의 종류와 수(보통주식 (주))",
            "nstk_estk_cnt": "신주의 종류와 수(기타주식 (주))",
            "fv_ps": "1주당 액면가액 (원)",
            "bfic_tisstk_ostk": "증자전 발행주식총수 (주)(보통주식 (주))",
            "bfic_tisstk_estk": "증자전 발행주식총수 (주)(기타주식 (주))",
            "nstk_asstd": "신주배정기준일",
            "nstk_ascnt_ps_ostk": "1주당 신주배정 주식수(보통주식 (주))",
            "nstk_ascnt_ps_estk": "1주당 신주배정 주식수(기타주식 (주))",
            "nstk_dividrk": "신주의 배당기산일",
            "nstk_dlprd": "신주권교부예정일",
            "nstk_lstprd": "신주의 상장 예정일",
            **_COMMON_BOARD_FIELDS,
        },
    },
    "pifricDecsn": {
        "description": "유무상증자 결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "piic_nstk_ostk_cnt": "유상증자(신주의 종류와 수(보통주식 (주)))",
            "piic_nstk_estk_cnt": "유상증자(신주의 종류와 수(기타주식 (주)))",
            "piic_fv_ps": "유상증자(1주당 액면가액 (원))",
            "piic_bfic_tisstk_ostk": "유상증자(증자전 발행주식총수(보통주식 (주)))",
            "piic_bfic_tisstk_estk": "유상증자(증자전 발행주식총수(기타주식 (주)))",
            "piic_fdpp_fclt": "유상증자(자금조달의 목적(시설자금 (원)))",
            "piic_fdpp_bsninh": "유상증자(자금조달의 목적(영업양수자금 (원)))",
            "piic_fdpp_op": "유상증자(자금조달의 목적(운영자금 (원)))",
            "piic_fdpp_dtrp": "유상증자(자금조달의 목적(채무상환자금 (원)))",
            "piic_fdpp_ocsa": "유상증자(자금조달의 목적(타법인 증권 취득자금 (원)))",
            "piic_fdpp_etc": "유상증자(자금조달의 목적(기타자금 (원)))",
            "piic_ic_mthn": "유상증자(증자방식)",
            "fric_nstk_ostk_cnt": "무상증자(신주의 종류와 수(보통주식 (주)))",
            "fric_nstk_estk_cnt": "무상증자(신주의 종류와 수(기타주식 (주)))",
            "fric_fv_ps": "무상증자(1주당 액면가액 (원))",
            "fric_bfic_tisstk_ostk": "무상증자(증자전 발행주식총수(보통주식 (주)))",
            "fric_bfic_tisstk_estk": "무상증자(증자전 발행주식총수(기타주식 (주)))",
            "fric_nstk_asstd": "무상증자(신주배정기준일)",
            "fric_nstk_ascnt_ps_ostk": "무상증자(1주당 신주배정 주식수(보통주식 (주)))",
            "fric_nstk_ascnt_ps_estk": "무상증자(1주당 신주배정 주식수(기타주식 (주)))",
            "fric_nstk_dividrk": "무상증자(신주의 배당기산일)",
            "fric_nstk_dlprd": "무상증자(신주권교부예정일)",
            "fric_nstk_lstprd": "무상증자(신주의 상장 예정일)",
            "fric_bddd": "무상증자(이사회결의일(결정일))",
            "fric_od_a_at_t": "무상증자(사외이사 참석여부(참석(명)))",
            "fric_od_a_at_b": "무상증자(사외이사 참석여부(불참(명)))",
            "fric_adt_a_atn": "무상증자(감사(감사위원)참석 여부)",
            "ssl_at": "공매도 해당여부",
            "ssl_bgd": "공매도 시작일",
            "ssl_edd": "공매도 종료일",
        },
    },
    "crDecsn": {
        "description": "감자 결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "crstk_ostk_cnt": "감자주식의 종류와 수(보통주식 (주))",
            "crstk_estk_cnt": "감자주식의 종류와 수(기타주식 (주))",
            "fv_ps": "1주당 액면가액 (원)",
            "bfcr_cpt": "감자전후 자본금(감자전 (원))",
            "atcr_cpt": "감자전후 자본금(감자후 (원))",
            "bfcr_tisstk_ostk": "감자전후 발행주식수(보통주식(감자전 (원)))",
            "atcr_tisstk_ostk": "감자전후 발행주식수(보통주식(감자후 (원)))",
            "bfcr_tisstk_estk": "감자전후 발행주식수(기타주식(감자전 (원)))",
            "atcr_tisstk_estk": "감자전후 발행주식수(기타주식(감자후 (원)))",
            "cr_rt_ostk": "감자비율(보통주식 (%))",
            "cr_rt_estk": "감자비율(기타주식 (%))",
            "cr_std": "감자기준일",
            "cr_mth": "감자방법",
            "cr_rs": "감자사유",
            "crsc_gmtsck_prd": "감자일정(주주총회 예정일)",
            "crsc_trnmsppd": "감자일정(명의개서정지기간)",
            "crsc_osprpd": "감자일정(구주권 제출기간)",
            "crsc_trspprpd": "감자일정(매매거래 정지예정기간)",
            "crsc_osprpd_bgd": "감자일정(구주권 제출기간(시작일))",
            "crsc_osprpd_edd": "감자일정(구주권 제출기간(종료일))",
            "crsc_trspprpd_bgd": "감자일정(매매거래 정지예정기간(시작일))",
            "crsc_trspprpd_edd": "감자일정(매매거래 정지예정기간(종료일))",
            "crsc_nstkdlprd": "감자일정(신주권교부예정일)",
            "crsc_nstklstprd": "감자일정(신주상장예정일)",
            "cdobprpd_bgd": "채권자 이의제출기간(시작일)",
            "cdobprpd_edd": "채권자 이의제출기간(종료일)",
            "ospr_nstkdl_pl": "구주권제출 및 신주권교부장소",
            **_COMMON_BOARD_FIELDS,
            "ftc_stt_atn": "공정거래위원회 신고대상 여부",
        },
    },
    "bnkMngtPcbg": {
        "description": "채권은행 등의 관리절차 개시",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "mngt_pcbg_dd": "관리절차개시 결정일자",
            "mngt_int": "관리기관",
            "mngt_pd": "관리기간",
            "mngt_rs": "관리사유",
            "cfd": "확인일자",
        },
    },
    "lwstLg": {
        "description": "소송 등의 제기",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "icnm": "사건의 명칭",
            "ac_ap": "원고ㆍ신청인",
            "rq_cn": "청구내용",
            "cpct": "관할법원",
            "ft_ctp": "향후대책",
            "lgd": "제기일자",
            "cfd": "확인일자",
        },
    },
    "ovLstDecsn": {
        "description": "해외 증권시장 주권등 상장 결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "lstprstk_ostk_cnt": "상장예정주식 종류ㆍ수(주)(보통주식)",
            "lstprstk_estk_cnt": "상장예정주식 종류ㆍ수(주)(기타주식)",
            "tisstk_ostk": "발행주식 총수(주)(보통주식)",
            "tisstk_estk": "발행주식 총수(주)(기타주식)",
            "psmth_nstk_sl": "공모방법(신주발행 (주))",
            "psmth_ostk_sl": "공모방법(구주매출 (주))",
            "fdpp": "자금조달(신주발행) 목적",
            "lststk_orlst": "상장증권(원주상장 (주))",
            "lststk_drlst": "상장증권(DR상장 (주))",
            "lstex_nt": "상장거래소(소재국가)",
            "lstpp": "해외상장목적",
            "lstprd": "상장예정일자",
            **_COMMON_BOARD_FIELDS,
        },
    },
    "ovDlstDecsn": {
        "description": "해외 증권시장 주권등 상장폐지 결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "dlststk_ostk_cnt": "상장폐지주식 종류ㆍ수(주)(보통주식)",
            "dlststk_estk_cnt": "상장폐지주식 종류ㆍ수(주)(기타주식)",
            "lstex_nt": "상장거래소(소재국가)",
            "dlstrq_prd": "폐지신청예정일자",
            "dlst_prd": "폐지(예정)일자",
            "dlst_rs": "폐지사유",
            "bddd": "이사회결의일(확인일)",
            "od_a_at_t": "사외이사 참석여부(참석(명))",
            "od_a_at_b": "사외이사 참석여부(불참(명))",
            "adt_a_atn": "감사(감사위원)참석여부",
        },
    },
    "ovLst": {
        "description": "해외 증권시장 주권등 상장",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "lststk_ostk_cnt": "상장주식 종류 및 수(보통주식(주))",
            "lststk_estk_cnt": "상장주식 종류 및 수(기타주식(주))",
            "lstex_nt": "상장거래소(소재국가)",
            "stk_cd": "종목 명 (code)",
            "lstd": "상장일자",
            "cfd": "확인일자",
        },
    },
    "ovDlst": {
        "description": "해외 증권시장 주권등 상장폐지",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "lstex_nt": "상장거래소 및 소재국가",
            "dlststk_ostk_cnt": "상장폐지주식의 종류(보통주식(주))",
            "dlststk_estk_cnt": "상장폐지주식의 종류(기타주식(주))",
            "tredd": "매매거래종료일",
            "dlst_rs": "폐지사유",
            "cfd": "확인일자",
        },
    },
    "cvbdIsDecsn": {
        "description": "전환사채권 발행결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            **_COMMON_BOND_FIELDS,
            "atcsc_rmislmt": "정관상 잔여 발행한도 (원)",
            "cv_rt": "전환에 관한 사항(전환비율 (%))",
            "cv_prc": "전환에 관한 사항(전환가액 (원/주))",
            "cvisstk_knd": "전환에 관한 사항(전환에 따라 발행할 주식(종류))",
            "cvisstk_cnt": "전환에 관한 사항(전환에 따라 발행할 주식(주식수))",
            "cvisstk_tisstk_vs": "전환에 관한 사항(전환에 따라 발행할 주식(주식총수 대비 비율(%)))",
            "cvrqpd_bgd": "전환에 관한 사항(전환청구기간(시작일))",
            "cvrqpd_edd": "전환에 관한 사항(전환청구기간(종료일))",
            "act_mktprcfl_cvprc_lwtrsprc": "전환에 관한 사항(시가하락에 따른 전환가액 조정(최저 조정가액 (원)))",
            "act_mktprcfl_cvprc_lwtrsprc_bs": "전환에 관한 사항(시가하락에 따른 전환가액 조정(최저 조정가액 근거))",
            "rmislmt_lt70p": "전환에 관한 사항(발행당시 전환가액의 70% 미만으로 조정가능한 잔여 발행한도 (원))",
            "abmg": "합병 관련 사항",
            **_COMMON_BOARD_FIELDS,
        },
    },
    "bdwtIsDecsn": {
        "description": "신주인수권부사채권 발행결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            **_COMMON_BOND_FIELDS,
            "atcsc_rmislmt": "정관상 잔여 발행한도 (원)",
            "ex_rt": "신주인수권에 관한 사항(행사비율 (%))",
            "ex_prc": "신주인수권에 관한 사항(행사가액 (원/주))",
            "ex_prc_dmth": "신주인수권에 관한 사항(행사가액 결정방법)",
            "bdwt_div_atn": "신주인수권에 관한 사항(사채와 인수권의 분리여부)",
            "nstk_pym_mth": "신주인수권에 관한 사항(신주대금 납입방법)",
            "nstk_isstk_knd": "신주인수권에 관한 사항(신주인수권 행사에 따라 발행할 주식(종류))",
            "nstk_isstk_cnt": "신주인수권에 관한 사항(신주인수권 행사에 따라 발행할 주식(주식수))",
            "nstk_isstk_tisstk_vs": "신주인수권에 관한 사항(신주인수권 행사에 따라 발행할 주식(주식총수 대비 비율(%)))",
            "expd_bgd": "신주인수권에 관한 사항(권리행사기간(시작일))",
            "expd_edd": "신주인수권에 관한 사항(권리행사기간(종료일))",
            "act_mktprcfl_cvprc_lwtrsprc": "신주인수권에 관한 사항(시가하락에 따른 행사가액 조정(최저 조정가액 (원)))",
            "act_mktprcfl_cvprc_lwtrsprc_bs": "신주인수권에 관한 사항(시가하락에 따른 행사가액 조정(최저 조정가액 근거))",
            "rmislmt_lt70p": "신주인수권에 관한 사항(발행당시 행사가액의 70% 미만으로 조정가능한 잔여 발행한도 (원))",
            "abmg": "합병 관련 사항",
            **_COMMON_BOARD_FIELDS,
        },
    },
    "exbdIsDecsn": {
        "description": "교환사채권 발행결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            **_COMMON_BOND_FIELDS,
            "ex_rt": "교환에 관한 사항(교환비율 (%))",
            "ex_prc": "교환에 관한 사항(교환가액 (원/주))",
            "ex_prc_dmth": "교환에 관한 사항(교환가액 결정방법)",
            "extg": "교환에 관한 사항(교환대상(종류))",
            "extg_stkcnt": "교환에 관한 사항(교환대상(주식수))",
            "extg_tisstk_vs": "교환에 관한 사항(교환대상(주식총수 대비 비율(%)))",
            "exrqpd_bgd": "교환에 관한 사항(교환청구기간(시작일))",
            "exrqpd_edd": "교환에 관한 사항(교환청구기간(종료일))",
            **_COMMON_BOARD_FIELDS,
        },
    },
    "bnkMngtPcsp": {
        "description": "채권은행 등의 관리절차 중단",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "mngt_pcsp_dd": "관리절차중단 결정일자",
            "mngt_int": "관리기관",
            "sp_rs": "중단사유",
            "ft_ctp": "향후대책",
            "cfd": "확인일자",
        },
    },
    "wdCocobdIsDecsn": {
        "description": "상각형 조건부자본증권 발행결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            **_COMMON_BOND_FIELDS,
            "dbtrs_sc": "채무재조정에 관한 사항(채무재조정의 범위)",
            **_COMMON_BOARD_FIELDS,
        },
    },
    "tsstkAqDecsn": {
        "description": "자기주식 취득 결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "aqpln_stk_ostk": "취득예정주식(주)(보통주식)",
            "aqpln_stk_estk": "취득예정주식(주)(기타주식)",
            "aqpln_prc_ostk": "취득예정금액(원)(보통주식)",
            "aqpln_prc_estk": "취득예정금액(원)(기타주식)",
            "aqexpd_bgd": "취득예상기간(시작일)",
            "aqexpd_edd": "취득예상기간(종료일)",
            "hdexpd_bgd": "보유예상기간(시작일)",
            "hdexpd_edd": "보유예상기간(종료일)",
            "aq_pp": "취득목적",
            "aq_mth": "취득방법",
            "cs_iv_bk": "위탁투자중개업자",
            "aq_wtn_div_ostk": "취득 전 자기주식 보유현황(배당가능이익 범위 내 취득(주)(보통주식))",
            "aq_wtn_div_ostk_rt": "취득 전 자기주식 보유현황(배당가능이익 범위 내 취득(주)(비율(%)))",
            "aq_wtn_div_estk": "취득 전 자기주식 보유현황(배당가능이익 범위 내 취득(주)(기타주식))",
            "aq_wtn_div_estk_rt": "취득 전 자기주식 보유현황(배당가능이익 범위 내 취득(주)(비율(%)))",
            "eaq_ostk": "취득 전 자기주식 보유현황(기타취득(주)(보통주식))",
            "eaq_ostk_rt": "취득 전 자기주식 보유현황(기타취득(주)(비율(%)))",
            "eaq_estk": "취득 전 자기주식 보유현황(기타취득(주)(기타주식))",
            "eaq_estk_rt": "취득 전 자기주식 보유현황(기타취득(주)(비율(%)))",
            "aq_dd": "취득결정일",
            "od_a_at_t": "사외이사참석여부(참석(명))",
            "od_a_at_b": "사외이사참석여부(불참(명))",
            "adt_a_atn": "감사(사외이사가 아닌 감사위원)참석여부",
            "d1_prodlm_ostk": "1일 매수 주문수량 한도(보통주식)",
            "d1_prodlm_estk": "1일 매수 주문수량 한도(기타주식)",
        },
    },
    "tsstkDpDecsn": {
        "description": "자기주식 처분 결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "dppln_stk_ostk": "처분예정주식(주)(보통주식)",
            "dppln_stk_estk": "처분예정주식(주)(기타주식)",
            "dpstk_prc_ostk": "처분 대상 주식가격(원)(보통주식)",
            "dpstk_prc_estk": "처분 대상 주식가격(원)(기타주식)",
            "dppln_prc_ostk": "처분예정금액(원)(보통주식)",
            "dppln_prc_estk": "처분예정금액(원)(기타주식)",
            "dpprpd_bgd": "처분예정기간(시작일)",
            "dpprpd_edd": "처분예정기간(종료일)",
            "dp_pp": "처분목적",
            "dp_m_mkt": "처분방법(시장을 통한 매도(주))",
            "dp_m_ovtm": "처분방법(시간외대량매매(주))",
            "dp_m_otc": "처분방법(장외처분(주))",
            "dp_m_etc": "처분방법(기타(주))",
            "cs_iv_bk": "위탁투자중개업자",
            "aq_wtn_div_ostk": "처분 전 자기주식 보유현황(배당가능이익 범위 내 취득(주)(보통주식))",
            "aq_wtn_div_ostk_rt": "처분 전 자기주식 보유현황(배당가능이익 범위 내 취득(주)(비율(%)))",
            "aq_wtn_div_estk": "처분 전 자기주식 보유현황(배당가능이익 범위 내 취득(주)(기타주식))",
            "aq_wtn_div_estk_rt": "처분 전 자기주식 보유현황(배당가능이익 범위 내 취득(주)(비율(%)))",
            "eaq_ostk": "처분 전 자기주식 보유현황(기타취득(주)(보통주식))",
            "eaq_ostk_rt": "처분 전 자기주식 보유현황(기타취득(주)(비율(%)))",
            "eaq_estk": "처분 전 자기주식 보유현황(기타취득(주)(기타주식))",
            "eaq_estk_rt": "처분 전 자기주식 보유현황(기타취득(주)(비율(%)))",
            "dp_dd": "처분결정일",
            "od_a_at_t": "사외이사참석여부(참석(명))",
            "od_a_at_b": "사외이사참석여부(불참(명))",
            "adt_a_atn": "감사(사외이사가 아닌 감사위원)참석여부",
            "d1_slodlm_ostk": "1일 매도 주문수량 한도(보통주식)",
            "d1_slodlm_estk": "1일 매도 주문수량 한도(기타주식)",
        },
    },
    "otcprStkInvscrTrfDecsn": {
        "description": "타법인 주식 및 출자 증권 양도결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "iscmp_cmpnm": "발행회사(회사명)",
            "iscmp_nt": "발행회사(국적)",
            "iscmp_rp": "발행회사(대표자)",
            "iscmp_cpt": "발행회사(자본금(원))",
            "iscmp_rl_cmpn": "발행회사(회사와 관계)",
            "iscmp_tisstk": "발행회사(발행주식 총수(주))",
            "iscmp_mbsn": "발행회사(주요사업)",
            "trfdtl_stkcnt": "양도내역(양도주식수(주))",
            "trfdtl_trfprc": "양도내역(양도금액(원))",
            "trfdtl_blttstd": "양도내역(대상주식의 장부가액)",
            "trfdtl_blttstd_vs": "양도내역(장부가액 대비 비율)",
            "trfdtl_oq_totqy": "양도 전 보유주식수",
            "trfdtl_oq_vs": "양도 후 보유비율",
            "trf_pp": "양도목적",
            "trf_rs": "양도사유",
            "trf_af": "양도영향",
            "trf_prd_ctr_cnsd": "양도예정일자(계약체결일)",
            "trf_prd_trf_xpctd": "양도예정일자(양도기준일)",
        },
    },
    "tgastTrfDecsn": {
        "description": "유형자산 양도 결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "ast_sen": "자산구분",
            "ast_nm": "자산명",
            "trfdtl_trfprc": "양도내역(양도금액(원))",
            "trfdtl_tast": "양도내역(자산총액)",
            "trfdtl_tast_vs": "양도내역(자산총액대비 비율)",
            "trf_pp": "양도목적",
            "trf_af": "양도영향",
            "trf_prd_ctr_cnsd": "양도예정일자(계약체결일)",
            "trf_prd_trf_xpctd": "양도예정일자(양도기준일)",
        },
    },
    "tgastInhDecsn": {
        "description": "유형자산 양수 결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "ast_sen": "자산구분",
            "ast_nm": "자산명",
            "inhdtl_inhprc": "양수내역(양수금액(원))",
            "inhdtl_tast": "양수내역(자산총액)",
            "inhdtl_tast_vs": "양수내역(자산총액대비 비율)",
            "inh_pp": "양수목적",
            "inh_af": "양수영향",
            "inh_prd_ctr_cnsd": "양수예정일자(계약체결일)",
            "inh_prd_inh_xpctd": "양수예정일자(양수기준일)",
        },
    },
    "otcprStkInvscrInhDecsn": {
        "description": "타법인 주식 및 출자증권 양수결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "iscmp_cmpnm": "발행회사(회사명)",
            "iscmp_nt": "발행회사(국적)",
            "iscmp_rp": "발행회사(대표자)",
            "iscmp_cpt": "발행회사(자본금(원))",
            "iscmp_rl_cmpn": "발행회사(회사와 관계)",
            "iscmp_tisstk": "발행회사(발행주식 총수(주))",
            "iscmp_mbsn": "발행회사(주요사업)",
            "inhdtl_inhprc": "양수내역(양수금액(원))",
            "inhdtl_blttstd": "양수내역(대상주식의 장부가액)",
            "inhdtl_blttstd_vs": "양수내역(장부가액 대비 비율)",
            "inhdtl_oq_totqy": "양수 전 보유주식수",
            "inhdtl_oq_vs": "양수 후 보유비율",
            "inh_pp": "양수목적",
            "inh_rs": "양수사유",
            "inh_af": "양수영향",
            "inh_prd_ctr_cnsd": "양수예정일자(계약체결일)",
            "inh_prd_inh_xpctd": "양수예정일자(양수기준일)",
        },
    },
    "bsnTrfDecsn": {
        "description": "영업양도 결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "trf_bsn": "양도영업",
            "trf_bsn_mc": "양도영업 주요내용",
            "trf_prc": "양도가액(원)",
            "ast_trf_bsn": "재무내용(자산액(양도대상 영업부문(A)))",
            "ast_cmp_all": "재무내용(자산액(당사전체(B)))",
            "ast_rt": "재무내용(자산액 비중(%)(A/B))",
            "sl_trf_bsn": "재무내용(매출액(양도대상 영업부문(A)))",
            "sl_cmp_all": "재무내용(매출액(당사전체(B)))",
            "sl_rt": "재무내용(매출액 비중(%)(A/B))",
            "op_prfi_trf_bsn": "재무내용(영업이익(양도대상 영업부문(A)))",
            "op_prfi_cmp_all": "재무내용(영업이익(당사전체(B)))",
            "op_prfi_rt": "재무내용(영업이익 비중(%)(A/B))",
            "trf_pp": "양도목적",
            "trf_af": "양도영향",
            "trf_prd_ctr_cnsd": "양도예정일자(계약체결일)",
            "trf_prd_trf_xpctd": "양도예정일자(양도기준일)",
        },
    },
    "bsnInhDecsn": {
        "description": "영업양수 결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "inh_bsn": "양수영업",
            "inh_bsn_mc": "양수영업 주요내용",
            "inh_prc": "양수가액(원)",
            "absn_inh_atn": "영업전부의 양수 여부",
            "ast_inh_bsn": "재무내용(자산액(양수대상 영업부문(A)))",
            "ast_cmp_all": "재무내용(자산액(당사전체(B)))",
            "ast_rt": "재무내용(자산액 비중(%)(A/B))",
            "sl_inh_bsn": "재무내용(매출액(양수대상 영업부문(A)))",
            "sl_cmp_all": "재무내용(매출액(당사전체(B)))",
            "sl_rt": "재무내용(매출액 비중(%)(A/B))",
            "op_prfi_inh_bsn": "재무내용(영업이익(양수대상 영업부문(A)))",
            "op_prfi_cmp_all": "재무내용(영업이익(당사전체(B)))",
            "op_prfi_rt": "재무내용(영업이익 비중(%)(A/B))",
            "inh_pp": "양수목적",
            "inh_af": "양수영향",
            "inh_prd_ctr_cnsd": "양수예정일자(계약체결일)",
            "inh_prd_inh_xpctd": "양수예정일자(양수기준일)",
        },
    },
    "tsstkAqTrctrCcDecsn": {
        "description": "자기주식취득 신탁계약 해지 결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "ctr_prc_bfcc": "계약금액(원)(해지 전)",
            "ctr_prc_atcc": "계약금액(원)(해지 후)",
            "ctr_pd_bfcc_bgd": "해지 전 계약기간(시작일)",
            "ctr_pd_bfcc_edd": "해지 전 계약기간(종료일)",
            "cc_pp": "해지목적",
            "cc_int": "해지기관",
            "cc_prd": "해지일자",
        },
    },
    "tsstkAqTrctrCnsDecsn": {
        "description": "자기주식취득 신탁계약 체결 결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "ctr_prc": "계약금액(원)",
            "ctr_pd_bgd": "계약기간(시작일)",
            "ctr_pd_edd": "계약기간(종료일)",
            "ctr_pp": "계약목적",
            "ctr_cns_int": "계약체결기관",
            "ctr_cns_prd": "계약체결 예정일자",
        },
    },
    "stkExtrDecsn": {
        "description": "주식교환·이전 결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "extr_sen": "구분",
            "extr_stn": "교환ㆍ이전 형태",
            "extr_tgcmp_cmpnm": "교환ㆍ이전 대상법인(회사명)",
            "extr_tgcmp_rp": "교환ㆍ이전 대상법인(대표자)",
            "extr_tgcmp_mbsn": "교환ㆍ이전 대상법인(주요사업)",
            "extr_tgcmp_rl_cmpn": "교환ㆍ이전 대상법인(회사와의 관계)",
        },
    },
    "cmpDvmgDecsn": {
        "description": "회사분할합병 결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "dvmg_mth": "분할합병 방법",
            "dvmg_impef": "분할합병의 중요영향 및 효과",
            "dv_trfbsnprt_cn": "분할에 관한 사항(분할로 이전할 사업 및 재산의 내용)",
        },
    },
    "cmpDvDecsn": {
        "description": "회사분할 결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "dv_mth": "분할방법",
            "dv_impef": "분할의 중요영향 및 효과",
            "dv_rt": "분할비율",
            "dv_trfbsnprt_cn": "분할로 이전할 사업 및 재산의 내용",
            "atdv_excmp_cmpnm": "분할 후 존속회사(회사명)",
        },
    },
    "cmpMgDecsn": {
        "description": "회사합병 결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "mg_mth": "합병방법",
            "mg_stn": "합병형태",
            "mg_pp": "합병목적",
            "mg_rt": "합병비율",
            "mg_rt_bs": "합병비율 산출근거",
            "exevl_atn": "외부평가 여부",
        },
    },
    "stkrtbdInhDecsn": {
        "description": "주권 관련 사채권 양수 결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "stkrtbd_kndn": "주권 관련 사채권의 종류",
            "tm": "회차",
            "knd": "종류",
            "bdiscmp_cmpnm": "사채권 발행회사(회사명)",
            "bdiscmp_nt": "사채권 발행회사(국적)",
            "bdiscmp_rp": "사채권 발행회사(대표자)",
        },
    },
    "stkrtbdTrfDecsn": {
        "description": "주권 관련 사채권 양도 결정",
        "fields": {
            **_COMMON_EVENT_FIELDS,
            "stkrtbd_kndn": "주권 관련 사채권의 종류",
            "tm": "회차",
            "knd": "종류",
            "aqd": "취득일자",
        },
    },
}


# ----- Regstate Catalogue (증권신고서 주요정보) ----- #
# source: https://opendart.fss.or.kr/guide/main.do?apiGrpCd=DS006

_COMMON_REGSTATE_FIELDS: _FieldMap = COMMON_RETURN_FIELDS

REGSTATE_RETURN_FIELDS_CATALOG: Dict[str, Dict] = {
    "estkRs": {
        "description": "증권신고서(지분증권)",
        "fields": {
            **_COMMON_REGSTATE_FIELDS,
            "sbd": "청약기일",
            "pymd": "납입기일",
            "sband": "청약공고일",
            "asand": "배정공고일",
            "asstd": "배정기준일",
            "exstk": "신주인수권에 관한 사항(행사대상증권)",
            "exprc": "신주인수권에 관한 사항(행사가격)",
            "expd": "신주인수권에 관한 사항(행사기간)",
            "rpt_rcpn": "주요사항보고서(접수번호)",
            "stksen": "증권의종류",
            "stkcnt": "증권수량",
            "fv": "액면가액",
            "slprc": "모집(매출)가액",
            "slta": "모집(매출)총액",
            "slmthn": "모집(매출)방법",
            "actsen": "인수인구분",
            "actnmn": "인수인명",
            "udtcnt": "인수수량",
            "udtamt": "인수금액",
            "udtprc": "인수대가",
            "udtmth": "인수방법",
            "se": "구분(자금의사용목적)",
            "amt": "금액(자금의사용목적)",
            "hdr": "보유자",
            "rl_cmp": "회사와의관계",
            "bfsl_hdstk": "매출전보유증권수",
            "slstk": "매출증권수",
            "atsl_hdstk": "매출후보유증권수",
            "grtrs": "부여사유(환매청구권)",
            "exavivr": "행사가능 투자자",
            "grtcnt": "부여수량",
        },
    },
    "bdRs": {
        "description": "증권신고서(채무증권)",
        "fields": {
            **_COMMON_REGSTATE_FIELDS,
            "tm": "회차",
            "bdnmn": "채무증권 명칭",
            "slmth": "모집(매출)방법",
            "fta": "권면(전자등록)총액",
            "slta": "모집(매출)총액",
            "isprc": "발행가액",
            "intr": "이자율",
            "isrr": "발행수익률",
            "rpd": "상환기일",
            "print_pymint": "원리금지급대행기관",
            "mngt_cmp": "(사채)관리회사",
            "cdrt_int": "신용등급(신용평가기관)",
            "sbd": "청약기일",
            "pymd": "납입기일",
            "sband": "청약공고일",
            "asand": "배정공고일",
            "asstd": "배정기준일",
            "dpcrn": "표시통화",
            "dpcr_amt": "표시통화기준발행규모",
            "usarn": "사용지역",
            "usntn": "사용국가",
            "wnexpl_at": "원화 교환 예정 여부",
            "grt_int": "보증기관",
            "grt_amt": "보증금액",
            "rpt_rcpn": "주요사항보고서(접수번호)",
            "drcb_at": "파생결합사채해당여부",
            "drcb_uast": "파생결합사채(기초자산)",
            "drcb_optknd": "파생결합사채(옵션종류)",
            "drcb_mtd": "파생결합사채(만기일)",
            "actsen": "인수인구분",
            "actnmn": "인수인명",
            "udtcnt": "인수수량",
            "udtamt": "인수금액",
            "udtprc": "인수대가",
            "udtmth": "인수방법",
            "se": "구분(자금의사용목적)",
            "amt": "금액(자금의사용목적)",
            "hdr": "보유자",
            "rl_cmp": "회사와의관계",
            "bfsl_hdstk": "매출전보유증권수",
            "slstk": "매출증권수",
            "atsl_hdstk": "매출후보유증권수",
        },
    },
    "stkdpRs": {
        "description": "증권신고서(증권예탁증권)",
        "fields": {
            **_COMMON_REGSTATE_FIELDS,
            "sbd": "청약기일",
            "pymd": "납입기일",
            "sband": "청약공고일",
            "asand": "배정공고일",
            "asstd": "배정기준일",
            "exstk": "신주인수권에 관한 사항(행사대상증권)",
            "exprc": "신주인수권에 관한 사항(행사가격)",
            "expd": "신주인수권에 관한 사항(행사기간)",
            "rpt_rcpn": "주요사항보고서(접수번호)",
            "stksen": "증권의종류",
            "stkcnt": "증권수량",
            "fv": "액면가액",
            "slprc": "모집(매출)가액",
            "slta": "모집(매출)총액",
            "slmthn": "모집(매출)방법",
            "actsen": "인수인구분",
            "actnmn": "인수인명",
            "udtcnt": "인수수량",
            "udtamt": "인수금액",
            "udtprc": "인수대가",
            "udtmth": "인수방법",
            "se": "구분(자금의사용목적)",
            "amt": "금액(자금의사용목적)",
            "hdr": "보유자",
            "rl_cmp": "회사와의관계",
            "bfsl_hdstk": "매출전보유증권수",
            "slstk": "매출증권수",
            "atsl_hdstk": "매출후보유증권수",
        },
    },
    "mgRs": {
        "description": "증권신고서(합병)",
        "fields": {
            **_COMMON_REGSTATE_FIELDS,
            "stn": "형태",
            "bddd": "이사회 결의일",
            "ctrd": "계약일",
            "gmtsck_shddstd": "주주총회를 위한 주주확정일",
            "ap_gmtsck": "승인을 위한 주주총회일",
            "aprskh_pd_bgd": "주식매수청구권 행사 기간(시작일)",
            "aprskh_pd_edd": "주식매수청구권 행사 기간(종료일)",
            "aprskh_prc": "주식매수청구가격(회사제시)",
            "mgdt_etc": "합병기일등",
            "rt_vl": "비율 또는 가액",
            "exevl_int": "외부평가기관",
            "grtmn_etc": "지급 교부금 등",
            "rpt_rcpn": "주요사항보고서(접수번호)",
            "kndn": "발행증권(종류)",
            "cnt": "발행증권(수량)",
            "fv": "발행증권(액면가액)",
            "slprc": "발행증권(모집(매출)가액)",
            "slta": "발행증권(모집(매출)총액)",
            "cmpnm": "당사회사(회사명)",
            "sen": "당사회사(구분)",
            "tast": "당사회사(총자산)",
            "cpt": "당사회사(자본금)",
            "isstk_knd": "당사회사(발행주식수(주식의종류))",
            "isstk_cnt": "당사회사(발행주식수(주식수))",
        },
    },
    "extrRs": {
        "description": "증권신고서(주식의포괄적교환·이전)",
        "fields": {
            **_COMMON_REGSTATE_FIELDS,
            "stn": "형태",
            "bddd": "이사회 결의일",
            "ctrd": "계약일",
            "gmtsck_shddstd": "주주총회를 위한 주주확정일",
            "ap_gmtsck": "승인을 위한 주주총회일",
            "aprskh_pd_bgd": "주식매수청구권 행사 기간(시작일)",
            "aprskh_pd_edd": "주식매수청구권 행사 기간(종료일)",
            "aprskh_prc": "주식매수청구가격(회사제시)",
            "mgdt_etc": "합병기일등",
            "rt_vl": "비율 또는 가액",
            "exevl_int": "외부평가기관",
            "grtmn_etc": "지급 교부금 등",
            "rpt_rcpn": "주요사항보고서(접수번호)",
            "kndn": "발행증권(종류)",
            "cnt": "발행증권(수량)",
            "fv": "발행증권(액면가액)",
            "slprc": "발행증권(모집(매출)가액)",
            "slta": "발행증권(모집(매출)총액)",
            "cmpnm": "당사회사(회사명)",
            "sen": "당사회사(구분)",
            "tast": "당사회사(총자산)",
            "cpt": "당사회사(자본금)",
            "isstk_knd": "당사회사(발행주식수(주식의종류))",
            "isstk_cnt": "당사회사(발행주식수(주식수))",
        },
    },
    "dvRs": {
        "description": "증권신고서(분할)",
        "fields": {
            **_COMMON_REGSTATE_FIELDS,
            "stn": "형태",
            "bddd": "이사회 결의일",
            "ctrd": "계약일",
            "gmtsck_shddstd": "주주총회를 위한 주주확정일",
            "ap_gmtsck": "승인을 위한 주주총회일",
            "aprskh_pd_bgd": "주식매수청구권 행사 기간(시작일)",
            "aprskh_pd_edd": "주식매수청구권 행사 기간(종료일)",
            "aprskh_prc": "주식매수청구가격(회사제시)",
            "mgdt_etc": "합병기일등",
            "rt_vl": "비율 또는 가액",
            "exevl_int": "외부평가기관",
            "grtmn_etc": "지급 교부금 등",
            "rpt_rcpn": "주요사항보고서(접수번호)",
            "kndn": "발행증권(종류)",
            "cnt": "발행증권(수량)",
            "fv": "발행증권(액면가액)",
            "slprc": "발행증권(모집(매출)가액)",
            "slta": "발행증권(모집(매출)총액)",
            "cmpnm": "당사회사(회사명)",
            "sen": "당사회사(구분)",
            "tast": "당사회사(총자산)",
            "cpt": "당사회사(자본금)",
            "isstk_knd": "당사회사(발행주식수(주식의종류))",
            "isstk_cnt": "당사회사(발행주식수(주식수))",
        },
    },
}

# ----- Report Catalogue (정기보고서 주요정보) ----- #
# source: https://opendart.fss.or.kr/guide/main.do?apiGrpCd=DS005

# report renames corp_name to 법인명 and adds 결산기준일.
_COMMON_REPORT_FIELDS: _FieldMap = {
    **COMMON_RETURN_FIELDS,
    "corp_name": "법인명",
    "stlm_dt": "결산기준일 (YYYY-MM-DD)",
}

REPORT_RETURN_FIELDS_CATALOG: Dict[str, Dict] = {
    "irdsSttus": {
        "description": "증자(감자) 현황",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "isu_dcrs_de": "주식발행 감소일자",
            "isu_dcrs_stle": "발행 감소 형태",
            "isu_dcrs_stock_knd": "발행 감소 주식 종류",
            "isu_dcrs_qy": "발행 감소 수량",
            "isu_dcrs_mstvdv_fval_amount": "발행 감소 주당 액면 가액",
            "isu_dcrs_mstvdv_amount": "발행 감소 주당 가액",
        },
    },
    "alotMatter": {
        "description": "배당에 관한 사항",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "se": "구분 (유상증자(주주배정), 전환권행사 등)",
            "stock_knd": "주식 종류 (보통주 등)",
            "thstrm": "당기",
            "frmtrm": "전기",
            "lwfr": "전전기",
        },
    },
    "tesstkAcqsDspsSttus": {
        "description": "자기주식 취득 및 처분 현황",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "acqs_mth1": "취득방법 대분류 (배당가능이익범위 이내 취득, 기타취득, 총계 등)",
            "acqs_mth2": "취득방법 중분류 (직접취득, 신탁계약에 의한취득, 기타취득, 총계 등)",
            "acqs_mth3": "취득방법 소분류 (장내직접취득, 장외직접취득, 공개매수 등)",
            "stock_knd": "주식 종류 (보통주, 우선주 등)",
            "bsis_qy": "기초 수량",
            "change_qy_acqs": "변동 수량 취득",
            "change_qy_dsps": "변동 수량 처분",
            "change_qy_incnr": "변동 수량 소각",
            "trmend_qy": "기말 수량",
            "rm": "비고",
        },
    },
    "hyslrSttus": {
        "description": "최대주주 현황",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "nm": "성명",
            "relate": "관계 (본인, 친인척 등)",
            "stock_knd": "주식 종류 (보통주 등)",
            "bsis_posesn_stock_co": "기초 소유 주식 수",
            "bsis_posesn_stock_qota_rt": "기초 소유 주식 지분 율",
            "trmend_posesn_stock_co": "기말 소유 주식 수",
            "trmend_posesn_stock_qota_rt": "기말 소유 주식 지분 율",
            "rm": "비고",
        },
    },
    "hyslrChgSttus": {
        "description": "최대주주 변동현황",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "change_on": "변동 일 (YYYY.MM.DD)",
            "mxmm_shrholdr_nm": "최대 주주 명",
            "posesn_stock_co": "소유 주식 수",
            "qota_rt": "지분 율",
            "change_cause": "변동 원인",
            "rm": "비고",
        },
    },
    "mrhlSttus": {
        "description": "소액주주 현황",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "se": "구분 (소액주주)",
            "shrholdr_co": "주주수",
            "shrholdr_tot_co": "전체 주주수",
            "shrholdr_rate": "주주 비율",
            "hold_stock_co": "보유 주식수",
            "stock_tot_co": "총발행 주식수",
            "hold_stock_rate": "보유 주식 비율",
        },
    },
    "exctvSttus": {
        "description": "임원 현황",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "nm": "성명",
            "sexdstn": "성별 (남)",
            "birth_ym": "출생 년월 (YYYY년 MM월)",
            "ofcps": "직위 (회장, 사장, 사외이사 등)",
            "rgist_exctv_at": "등기 임원 여부 (등기임원, 미등기임원 등)",
            "fte_at": "상근 여부 (상근, 비상근)",
            "chrg_job": "담당 업무 (대표이사, 이사, 사외이사 등)",
            "main_career": "주요 경력",
            "mxmm_shrholdr_relate": "최대 주주 관계",
            "hffc_pd": "재직 기간",
            "tenure_end_on": "임기 만료 일",
        },
    },
    "empSttus": {
        "description": "직원 현황",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "fo_bbm": "사업부문",
            "sexdstn": "성별 (남, 여)",
            "reform_bfe_emp_co_rgllbr": "개정 전 직원 수 정규직",
            "reform_bfe_emp_co_cnttk": "개정 전 직원 수 계약직",
            "reform_bfe_emp_co_etc": "개정 전 직원 수 기타",
            "rgllbr_co": "정규직 수",
            "rgllbr_abacpt_labrr_co": "정규직 단시간 근로자 수",
            "cnttk_co": "계약직 수",
            "cnttk_abacpt_labrr_co": "계약직 단시간 근로자 수",
            "sm": "합계",
            "avrg_cnwk_sdytrn": "평균 근속 연수",
            "fyer_salary_totamt": "연간 급여 총액",
            "jan_salary_am": "1인평균 급여 액",
            "rm": "비고",
        },
    },
    "hmvAuditIndvdlBySttus": {
        "description": "이사·감사의 개인별 보수현황(5억원 이상)",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "nm": "이름",
            "ofcps": "직위 (이사, 대표이사 등)",
            "mendng_totamt": "보수 총액",
            "mendng_totamt_ct_incls_mendng": "보수 총액 비 포함 보수",
        },
    },
    "hmvAuditAllSttus": {
        "description": "이사·감사 전체의 보수현황(보수지급금액 - 이사·감사 전체)",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "nmpr": "인원수",
            "mendng_totamt": "보수 총액",
            "jan_avrg_mendng_am": "1인 평균 보수 액",
            "rm": "비고",
        },
    },
    "indvdlByPay": {
        "description": "개인별 보수지급 금액(5억이상 상위5인)",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "nm": "이름",
            "ofcps": "직위 (대표이사 등)",
            "mendng_totamt": "보수 총액",
            "mendng_totamt_ct_incls_mendng": "보수 총액 비 포함 보수",
        },
    },
    "otrCprInvstmntSttus": {
        "description": "타법인 출자현황",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "inv_prm": "법인명",
            "frst_acqs_de": "최초 취득 일자 (YYYYMMDD)",
            "invstmnt_purps": "출자 목적 (자회사 등)",
            "frst_acqs_amount": "최초 취득 금액",
            "bsis_blce_qy": "기초 잔액 수량",
            "bsis_blce_qota_rt": "기초 잔액 지분 율",
            "bsis_blce_acntbk_amount": "기초 잔액 장부 가액",
            "incrs_dcrs_acqs_dsps_qy": "증가 감소 취득 처분 수량",
            "incrs_dcrs_acqs_dsps_amount": "증가 감소 취득 처분 금액",
            "incrs_dcrs_evl_lstmn": "증가 감소 평가 손액",
            "trmend_blce_qy": "기말 잔액 수량",
            "trmend_blce_qota_rt": "기말 잔액 지분 율",
            "trmend_blce_acntbk_amount": "기말 잔액 장부 가액",
            "recent_bsns_year_fnnr_sttus_tot_assets": "최근 사업 연도 재무 현황 총 자산",
            "recent_bsns_year_fnnr_sttus_thstrm_ntpf": "최근 사업 연도 재무 현황 당기 순이익",
        },
    },
    "stockTotqySttus": {
        "description": "주식의 총수 현황",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "se": "구분 (증권의종류, 합계, 비고)",
            "isu_stock_totqy": "발행할 주식의 총수",
            "now_to_isu_stock_totqy": "현재까지 발행한 주식의 총수",
            "now_to_dcrs_stock_totqy": "현재까지 감소한 주식의 총수",
            "redc": "감자",
            "profit_incnr": "이익소각",
            "rdmstk_repy": "상환주식의 상환",
            "etc": "기타",
            "istc_totqy": "발행주식의 총수",
            "tesstk_co": "자기주식수",
            "distb_stock_co": "유통주식수",
        },
    },
    "detScritsIsuAcmslt": {
        "description": "채무증권 발행실적",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "isu_cmpny": "발행회사",
            "scrits_knd_nm": "증권종류",
            "isu_mth_nm": "발행방법",
            "isu_de": "발행일자 (YYYYMMDD)",
            "facvalu_totamt": "권면(전자등록)총액",
            "intrt": "이자율",
            "evl_grad_instt": "평가등급(평가기관)",
            "mtd": "만기일 (YYYYMMDD)",
            "repy_at": "상환여부",
            "mngt_cmpny": "주관회사",
        },
    },
    "entrprsBilScritsNrdmpBlce": {
        "description": "기업어음증권 미상환 잔액",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "remndr_exprtn1": "잔여만기(대분류)",
            "remndr_exprtn2": "잔여만기(소분류)",
            "de10_below": "10일 이하",
            "de10_excess_de30_below": "10일초과 30일이하",
            "de30_excess_de90_below": "30일초과 90일이하",
            "de90_excess_de180_below": "90일초과 180일이하",
            "de180_excess_yy1_below": "180일초과 1년이하",
            "yy1_excess_yy2_below": "1년초과 2년이하",
            "yy2_excess_yy3_below": "2년초과 3년이하",
            "yy3_excess": "3년 초과",
            "sm": "합계",
        },
    },
    "srtpdPsndbtNrdmpBlce": {
        "description": "단기사채 미상환 잔액",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "remndr_exprtn1": "잔여만기(대분류)",
            "remndr_exprtn2": "잔여만기(소분류)",
            "de10_below": "10일 이하",
            "de10_excess_de30_below": "10일초과 30일이하",
            "de30_excess_de90_below": "30일초과 90일이하",
            "de90_excess_de180_below": "90일초과 180일이하",
            "de180_excess_yy1_below": "180일초과 1년이하",
            "sm": "합계",
            "isu_lmt": "발행 한도",
            "remndr_lmt": "잔여 한도",
        },
    },
    "cprndNrdmpBlce": {
        "description": "회사채 미상환 잔액",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "remndr_exprtn1": "잔여만기(대분류)",
            "remndr_exprtn2": "잔여만기(소분류)",
            "yy1_below": "1년 이하",
            "yy1_excess_yy2_below": "1년초과 2년이하",
            "yy2_excess_yy3_below": "2년초과 3년이하",
            "yy3_excess_yy4_below": "3년초과 4년이하",
            "yy4_excess_yy5_below": "4년초과 5년이하",
            "yy5_excess_yy10_below": "5년초과 10년이하",
            "yy10_excess": "10년초과",
            "sm": "합계",
        },
    },
    "newCaplScritsNrdmpBlce": {
        "description": "신종자본증권 미상환 잔액",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "remndr_exprtn1": "잔여만기(대분류)",
            "remndr_exprtn2": "잔여만기(소분류)",
            "yy1_below": "1년 이하",
            "yy1_excess_yy5_below": "1년초과 5년이하",
            "yy5_excess_yy10_below": "5년초과 10년이하",
            "yy10_excess_yy15_below": "10년초과 15년이하",
            "yy15_excess_yy20_below": "15년초과 20년이하",
            "yy20_excess_yy30_below": "20년초과 30년이하",
            "yy30_excess": "30년초과",
            "sm": "합계",
        },
    },
    "cndlCaplScritsNrdmpBlce": {
        "description": "조건부 자본증권 미상환 잔액",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "remndr_exprtn1": "잔여만기(대분류)",
            "remndr_exprtn2": "잔여만기(소분류)",
            "yy1_below": "1년 이하",
            "yy1_excess_yy2_below": "1년초과 2년이하",
            "yy2_excess_yy3_below": "2년초과 3년이하",
            "yy3_excess_yy4_below": "3년초과 4년이하",
            "yy4_excess_yy5_below": "4년초과 5년이하",
            "yy5_excess_yy10_below": "5년초과 10년이하",
            "yy10_excess_yy20_below": "10년초과 20년이하",
            "yy20_excess_yy30_below": "20년초과 30년이하",
            "yy30_excess": "30년초과",
            "sm": "합계",
        },
    },
    "accnutAdtorNmNdAdtOpinion": {
        "description": "회계감사인의 명칭 및 감사의견",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "bsns_year": "사업연도 (당기, 전기, 전전기)",
            "adtor": "감사인",
            "adt_opinion": "감사의견",
            "adt_reprt_spcmnt_matter": "감사보고서 특기사항 (2019년 12월 8일까지 사용됨)",
            "emphs_matter": "강조사항 등 (2019년 12월 9일부터 추가됨)",
            "core_adt_matter": "핵심감사사항 (2019년 12월 9일부터 추가됨)",
        },
    },
    "adtServcCnclsSttus": {
        "description": "감사용역체결현황",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "bsns_year": "사업연도 (당기, 전기, 전전기)",
            "adtor": "감사인",
            "cn": "내용",
            "mendng": "보수 (2020년 7월 5일까지 사용됨)",
            "tot_reqre_time": "총소요시간 (2020년 7월 5일까지 사용됨)",
            "adt_cntrct_dtls_mendng": "감사계약내역(보수) (2020년 7월 6일부터 추가됨)",
            "adt_cntrct_dtls_time": "감사계약내역(시간) (2020년 7월 6일부터 추가됨)",
            "real_exc_dtls_mendng": "실제수행내역(보수) (2020년 7월 6일부터 추가됨)",
            "real_exc_dtls_time": "실제수행내역(시간) (2020년 7월 6일부터 추가됨)",
        },
    },
    "accnutAdtorNonAdtServcCnclsSttus": {
        "description": "회계감사인과의 비감사용역 계약체결 현황",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "bsns_year": "사업연도 (당기, 전기, 전전기)",
            "cntrct_cncls_de": "계약체결일",
            "servc_cn": "용역내용",
            "servc_exc_pd": "용역수행기간",
            "servc_mendng": "용역보수",
            "rm": "비고",
        },
    },
    "outcmpnyDrctrNdChangeSttus": {
        "description": "사외이사 및 그 변동현황",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "drctr_co": "이사의 수",
            "otcmp_drctr_co": "사외이사 수",
            "apnt": "사외이사 변동현황(선임)",
            "rlsofc": "사외이사 변동현황(해임)",
            "mdstrm_resig": "사외이사 변동현황(중도퇴임)",
        },
    },
    "unrstExctvMendngSttus": {
        "description": "미등기임원 보수현황",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "se": "구분 (미등기임원)",
            "nmpr": "인원수",
            "fyer_salary_totamt": "연간급여 총액",
            "jan_salary_am": "1인평균 급여액",
            "rm": "비고",
        },
    },
    "drctrAdtAllMendngSttusGmtsckConfmAmount": {
        "description": "이사·감사 전체의 보수현황(주주총회 승인금액)",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "se": "구분",
            "nmpr": "인원수",
            "gmtsck_confm_amount": "주주총회 승인금액",
            "rm": "비고",
        },
    },
    "drctrAdtAllMendngSttusMendngPymntamtTyCl": {
        "description": "이사·감사 전체의 보수현황(보수지급금액 - 유형별)",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "se": "구분",
            "nmpr": "인원수",
            "pymnt_totamt": "보수총액",
            "psn1_avrg_pymntamt": "1인당 평균보수액",
            "rm": "비고",
        },
    },
    "pssrpCptalUseDtls": {
        "description": "공모자금의 사용내역",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "se_nm": "구분",
            "tm": "회차 (2019년 12월 9일부터 추가됨)",
            "pay_de": "납입일",
            "pay_amount": "납입금액 (2018년 1월 18일까지 사용됨)",
            "on_dclrt_cptal_use_plan": "신고서상 자금사용 계획 (2018년 1월 18일까지 사용됨)",
            "real_cptal_use_sttus": "실제 자금사용 현황 (2018년 1월 18일까지 사용됨)",
            "rs_cptal_use_plan_useprps": "증권신고서 등의 자금사용 계획(사용용도) (2018년 1월 19일부터 추가됨)",
            "rs_cptal_use_plan_prcure_amount": "증권신고서 등의 자금사용 계획(조달금액) (2018년 1월 19일부터 추가됨)",
            "real_cptal_use_dtls_cn": "실제 자금사용 내역(내용) (2018년 1월 19일부터 추가됨)",
            "real_cptal_use_dtls_amount": "실제 자금사용 내역(금액) (2018년 1월 19일부터 추가됨)",
            "dffrnc_occrrnc_resn": "차이발생 사유 등",
        },
    },
    "prvsrpCptalUseDtls": {
        "description": "사모자금의 사용내역",
        "fields": {
            **_COMMON_REPORT_FIELDS,
            "se_nm": "구분",
            "tm": "회차 (2019년 12월 9일부터 추가됨)",
            "pay_de": "납입일",
            "pay_amount": "납입금액 (2018년 1월 18일까지 사용됨)",
            "cptal_use_plan": "자금사용 계획 (2018년 1월 18일까지 사용됨)",
            "real_cptal_use_sttus": "실제 자금사용 현황 (2018년 1월 18일까지 사용됨)",
            "mtrpt_cptal_use_plan_useprps": "주요사항보고서의 자금사용 계획(사용용도) (2018년 1월 19일부터 추가됨)",
            "mtrpt_cptal_use_plan_prcure_amount": "주요사항보고서의 자금사용 계획(조달금액) (2018년 1월 19일부터 추가됨)",
            "real_cptal_use_dtls_cn": "실제 자금사용 내역(내용) (2018년 1월 19일부터 추가됨)",
            "real_cptal_use_dtls_amount": "실제 자금사용 내역(금액) (2018년 1월 19일부터 추가됨)",
            "dffrnc_occrrnc_resn": "차이발생 사유 등",
        },
    },
}
# ----- Share Catalogue (지분공시 종합정보) ----- #
# source: https://opendart.fss.or.kr/guide/main.do?apiGrpCd=DS004
# Share endpoints drop corp_cls and use rcept_dt(YYYY-MM-DD); corp_name covers
# both 상장사 종목명 and 기타법인 법인명.
_COMMON_SHARE_FIELDS: _FieldMap = {
    "rcept_no": COMMON_RETURN_FIELDS["rcept_no"],
    "rcept_dt": "접수일자 (공시 접수일자 YYYY-MM-DD)",
    "corp_code": COMMON_RETURN_FIELDS["corp_code"],
    "corp_name": "회사명 (공시대상회사의 종목명(상장사) 또는 법인명(기타법인))",
}

_MAJORSTOCK_FIELDS: _FieldMap = {
    **_COMMON_SHARE_FIELDS,
    "report_tp": "보고구분 (주식등의 대량보유상황 보고구분)",
    "repror": "대표보고자",
    "stkqy": "보유주식등의 수",
    "stkqy_irds": "보유주식등의 증감",
    "stkrt": "보유비율",
    "stkrt_irds": "보유비율 증감",
    "ctr_stkqy": "주요체결 주식등의 수",
    "ctr_stkrt": "주요체결 보유비율",
    "report_resn": "보고사유",
}
_ELESTOCK_FIELDS: _FieldMap = {
    **_COMMON_SHARE_FIELDS,
    "repror": "보고자명",
    "isu_exctv_rgist_at": "발행 회사 관계 임원(등기여부) (등기임원, 비등기임원 등)",
    "isu_exctv_ofcps": "발행 회사 관계 임원 직위 (대표이사, 이사, 전무 등)",
    "isu_main_shrholdr": "발행 회사 관계 주요 주주 (10%이상주주 등)",
    "sp_stock_lmp_cnt": "특정 증권 등 소유 수",
    "sp_stock_lmp_irds_cnt": "특정 증권 등 소유 증감 수",
    "sp_stock_lmp_rate": "특정 증권 등 소유 비율",
    "sp_stock_lmp_irds_rate": "특정 증권 등 소유 증감 비율",
}

SHARE_RETURN_FIELDS_CATALOG: Dict[str, Dict] = {
    "majorstock": {
        "description": "주식등의 대량보유상황보고서",
        "fields": _MAJORSTOCK_FIELDS,
    },
    "elestock": {
        "description": "임원ㆍ주요주주특정증권등 소유상황보고서",
        "fields": _ELESTOCK_FIELDS,
    },
}

# ----- Finstate Catalogue (상장기업 재무정보) ----- #
# source: https://opendart.fss.or.kr/guide/main.do?apiGrpCd=DS003
_COMMON_FINSTATE_FIELDS: _FieldMap = {
    "rcept_no": COMMON_RETURN_FIELDS["rcept_no"],
    "reprt_code": "보고서 코드",
    "bsns_year": "사업 연도",
    "sj_div": "재무제표구분 (BS:재무상태표, IS:손익계산서, CIS:포괄손익계산서, CF:현금흐름표, SCE:자본변동표)",
    "sj_nm": "재무제표명 (예: 재무상태표 또는 손익계산서)",
    "account_nm": "계정명 (예: 자본총계)",
    # thstrm_nm / thstrm_amount은 두 엔드포인트의 원본 설명이 달라 각 항목에 개별 정의함.
    "thstrm_add_amount": "당기누적금액",
    "frmtrm_nm": "전기명 (예: 제 12 기말)",
    "frmtrm_amount": "전기금액",
    "frmtrm_add_amount": "전기누적금액",
    "bfefrmtrm_nm": "전전기명 (사업보고서의 경우에만 출력)",
    "bfefrmtrm_amount": "전전기금액 (사업보고서의 경우에만 출력)",
    "ord": "계정과목 정렬순서",
    "currency": "통화 단위",
}

_FNLTTACNT_FIELDS: _FieldMap = {
    **_COMMON_FINSTATE_FIELDS,
    "stock_code": "종목 코드 (상장회사의 종목코드 6자리)",
    "fs_div": "개별/연결구분 (OFS:재무제표, CFS:연결재무제표)",
    "fs_nm": "개별/연결명 (예: 연결재무제표 또는 재무제표)",
    "thstrm_nm": "당기명 (예: 제 13 기 3분기말)",
    "thstrm_dt": "당기일자 (예: 2018.09.30 현재)",
    "thstrm_amount": "당기금액",
    "frmtrm_dt": "전기일자 (예: 2017.01.01 ~ 2017.12.31)",
    "bfefrmtrm_dt": "전전기일자 (사업보고서의 경우에만 출력)",
}
_FNLTTSINGLACNTALL_FIELDS: _FieldMap = {
    **_COMMON_FINSTATE_FIELDS,
    "corp_code": COMMON_RETURN_FIELDS["corp_code"],
    "account_id": '계정ID (XBRL 표준계정ID, 표준계정코드 미사용 시 ""-표준계정코드 미사용-"" 표시)',
    "account_detail": "계정상세 (자본변동표에만 출력, 예: 자본 [member]|지배기업 소유주지분)",
    "thstrm_nm": "당기명 (예: 제 13 기)",
    "thstrm_amount": "당기금액 (분/반기 보고서이면서 (포괄)손익계산서일 경우 [3개월] 금액)",
    "frmtrm_q_nm": "전기명(분/반기) (예: 제 18 기 반기)",
    "frmtrm_q_amount": "전기금액(분/반기) (분/반기 보고서이면서 (포괄)손익계산서일 경우 [3개월] 금액)",
}
# xbrlTaxonomy (표준계정과목체계) does not share common fields because it is metadata, not financial data.
_XBRLTAXONOMY_FIELDS: _FieldMap = {
    "sj_div": "재무제표구분",
    "account_id": "계정ID (계정 고유명칭)",
    "account_nm": "계정명",
    "bsns_de": "기준일 (적용 기준일)",
    "label_kor": "한글 출력명",
    "label_eng": "영문 출력명",
    "data_tp": (
        "데이터 유형. 다음 중 하나:\n"
        '    - "text block": 제목\n'
        '    - "Text": Text\n'
        '    - "yyyy-mm-dd": Date\n'
        '    - "X": Monetary Value\n'
        '    - "(X)": Monetary Value(Negative)\n'
        '    - "X.XX": Decimalized Value\n'
        '    - "Shares": Number of shares (주식 수)\n'
        '    - "For each": 공시된 항목이 전후로 반복적으로 공시될 경우 사용\n'
        "    - 공란: 입력 필요 없음"
    ),
    "ifrs_ref": "IFRS Reference (예: K-IFRS 1001 문단 54 (9),K-IFRS 1007 문단 45)",
}

FINSTATE_RETURN_FIELDS_CATALOG: Dict[str, Dict] = {
    "fnlttAcnt": {
        "description": "상장기업 재무정보(주요계정)",
        "fields": _FNLTTACNT_FIELDS,
    },
    "fnlttSinglAcntAll": {
        "description": "단일회사 전체 재무제표(전체계정)",
        "fields": _FNLTTSINGLACNTALL_FIELDS,
    },
    "xbrlTaxonomy": {
        "description": "XBRL 표준계정과목체계(계정과목)",
        "fields": _XBRLTAXONOMY_FIELDS,
    },
}

# ----- List Catalogue (공시정보) ----- #
# source: https://opendart.fss.or.kr/guide/main.do?apiGrpCd=DS001
_LIST_FIELDS: _FieldMap = {
    "corp_cls": COMMON_RETURN_FIELDS["corp_cls"],
    "corp_name": "종목명(법인명) (공시대상회사의 종목명(상장사) 또는 법인명(기타법인))",
    "corp_code": COMMON_RETURN_FIELDS["corp_code"],
    "stock_code": "종목코드 (상장회사의 종목코드 6자리)",
    "report_nm": "보고서명 (공시구분+보고서명+기타정보)",
    "rcept_no": COMMON_RETURN_FIELDS["rcept_no"],
    "flr_nm": "공시 제출인명",
    "rcept_dt": "접수일자 (공시 접수일자 YYYYMMDD)",
    "rm": (
        "비고. 조합된 문자로 각각은 아래와 같은 의미가 있음:\n"
        "    - 유: 본 공시사항은 한국거래소 유가증권시장본부 소관임\n"
        "    - 코: 본 공시사항은 한국거래소 코스닥시장본부 소관임\n"
        "    - 채: 본 문서는 한국거래소 채권상장법인 공시사항임\n"
        "    - 넥: 본 문서는 한국거래소 코넥스시장 소관임\n"
        "    - 공: 본 공시사항은 공정거래위원회 소관임\n"
        "    - 연: 본 보고서는 연결부분을 포함한 것임\n"
        "    - 정: 본 보고서 제출 후 정정신고가 있으니 관련 보고서를 참조하시기 바람\n"
        "    - 철: 본 보고서는 철회(간주)되었으니 관련 철회신고서(철회간주안내)를 참고하시기 바람"
    ),
}
_COMPANY_FIELDS: _FieldMap = {
    "corp_name": "정식명칭 (정식회사명칭)",
    "corp_name_eng": "영문명칭 (영문정식회사명칭)",
    "stock_name": "종목명(상장사) 또는 약식명칭(기타법인)",
    "stock_code": "상장회사인 경우 주식의 종목코드 (상장회사의 종목코드 6자리)",
    "ceo_nm": "대표자명",
    "corp_cls": COMMON_RETURN_FIELDS["corp_cls"],
    "jurir_no": "법인등록번호",
    "bizr_no": "사업자등록번호",
    "adres": "주소",
    "hm_url": "홈페이지",
    "ir_url": "IR홈페이지",
    "phn_no": "전화번호",
    "fax_no": "팩스번호",
    "induty_code": "업종코드",
    "est_dt": "설립일 (YYYYMMDD)",
    "acc_mt": "결산월 (MM)",
}
_CORPCODE_FIELDS: _FieldMap = {
    "corp_code": COMMON_RETURN_FIELDS["corp_code"],
    "corp_name": "정식명칭 (정식회사명칭)",
    "corp_eng_name": "영문 정식명칭 (영문정식회사명칭)",
    "stock_code": "종목코드 (상장회사인 경우 주식의 종목코드 6자리)",
    "modify_date": "최종변경일자 (기업개황정보 최종변경일자 YYYYMMDD)",
}

LIST_RETURN_FIELDS_CATALOG: Dict[str, Dict] = {
    "list": {
        "description": "공시정보 검색",
        "fields": _LIST_FIELDS,
    },
    "company": {
        "description": "기업개황정보",
        "fields": _COMPANY_FIELDS,
    },
    "corpCode": {
        "description": "공시대상회사 고유번호",
        "fields": _CORPCODE_FIELDS,
    },
}

DART_RETURN_FIELDS_CATALOGS: Dict[str, Dict[str, Dict]] = {
    "event": EVENT_RETURN_FIELDS_CATALOG,
    "report": REPORT_RETURN_FIELDS_CATALOG,
    "regstate": REGSTATE_RETURN_FIELDS_CATALOG,
    "share": SHARE_RETURN_FIELDS_CATALOG,
    "finstate": FINSTATE_RETURN_FIELDS_CATALOG,
    "list": LIST_RETURN_FIELDS_CATALOG,
}


def list_dart_return_fields_catalog(catalog_name: str) -> Dict[str, str]:
    """한 DART 카탈로그에 속한 아이템 목록과 각 설명을 조회합니다.
    (ex. `catalog_name=event` returns: {"dfOcr": "부도발생", "piicDecsn": "유상증자 결정", ...})

    각 카탈로그는 하나의 DART 서비스 그룹에 대응하며, 아이템 목록은 그 안의 개별 조회 단위입니다.
    아이템의 의미는 카탈로그 종류에 따라 다릅니다:
    - event/report/regstate: 단일 함수(event/report/regstate)의 함수 인자.
      (ex. "dfOcr", "irdsSttus", "estkRs")
    - share/finstate/list: 해당 서비스의 개별 함수 이름.
      (ex. "majorstock", "fnlttAcnt", "company")

    Args:
        catalog_name: 카탈로그 이름. 다음 중 하나여야 합니다: event, report, regstate, share, finstate, list
    """
    try:
        catalog = DART_RETURN_FIELDS_CATALOGS[catalog_name]
    except KeyError as exc:
        valid = sorted(DART_RETURN_FIELDS_CATALOGS)
        raise ValueError(f"Unknown catalog_name: {catalog_name!r}. Valid values: {valid}") from exc

    return {name: item["description"] for name, item in catalog.items()}


def get_dart_return_fields(catalog_name: str, item_type: str) -> Dict:
    """한 DART 카탈로그의 특정 아이템에 대한 반환 필드 메타데이터를 조회합니다.
    (ex. `catalog_name=event, item_type=dfOcr` returns:
     {"description": "부도발생", "fields": {"rcept_no": "접수번호(14자리)...", "df_cn": "부도내용", ...}})

    DART API 응답 배열의 각 항목이 어떤 필드를 담는지, 각 필드가 무엇을 의미하는지 확인할 때 사용합니다.
    사용 가능한 catalog_name/item_type 목록은 list_dart_return_fields_catalog()로 먼저 확인할 수 있습니다.

    아이템의 의미는 카탈로그 종류에 따라 다릅니다:
    - event/report/regstate: 단일 함수(event/report/regstate)의 함수 인자.
      (ex. "dfOcr", "irdsSttus", "estkRs")
    - share/finstate/list: 해당 서비스의 개별 함수 이름.
      (ex. "majorstock", "fnlttAcnt", "company")

    Args:
        catalog_name: 카탈로그 이름. 다음 중 하나여야 합니다: event, report, regstate, share, finstate, list
        item_type: 카탈로그 내 조회 단위. (ex. "dfOcr", "majorstock")
    """
    try:
        catalog = DART_RETURN_FIELDS_CATALOGS[catalog_name]
    except KeyError as exc:
        valid = sorted(DART_RETURN_FIELDS_CATALOGS)
        raise ValueError(f"Unknown catalog_name: {catalog_name!r}. Valid values: {valid}") from exc

    try:
        item = catalog[item_type]
    except KeyError as exc:
        valid = sorted(catalog)
        raise ValueError(f"Unknown item_type: {item_type!r}. Valid values: {valid}") from exc

    return item
