import difflib
import re
import time
from datetime import datetime
from io import StringIO
from typing import Any, Dict, List, Optional

import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests
from curl_cffi.requests.exceptions import Timeout as CurlCffiTimeout
from markdownify import markdownify as md

from .dart_parser import parse_dart_to_text


def html_to_markdown_keep_tables(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    table_md_map = {}
    tables = soup.find_all("table")

    for i, table in enumerate(tables):
        placeholder = f"TABLEPLACEHOLDER{i}TABLE"

        try:
            df = pd.read_html(StringIO(str(table)))[0]
            table_md = df.to_markdown(index=False, tablefmt="github")
        except Exception:
            table_md = "```html\n" + str(table) + "\n```"

        table_md_map[placeholder] = table_md
        table.replace_with(soup.new_string(placeholder))

    md_text = md(
        str(soup),
        heading_style="ATX",
        bullets="-",
        strip=["script", "style"],
    )

    for placeholder, table_md in table_md_map.items():
        md_text = md_text.replace(placeholder, table_md)

    # (Optional) Handle rare cases where markdownify inserts backslashes in placeholders
    for placeholder, table_md in table_md_map.items():
        md_text = md_text.replace(placeholder.replace("_", r"\_"), table_md)

    md_text = md_text.replace("\r\n", "\n")
    md_text = re.sub(r"\n{3,}", "\n\n", md_text).strip()

    return md_text


_BASE_URL = "https://dart.fss.or.kr"

_session = None


def _get_session():
    """Get a shared curl_cffi session with a simple connectivity test.

    DART endpoints are sensitive to transient TLS/network conditions; validating the
    session once at creation time reduces first-call flakiness.
    """
    global _session
    if _session is not None:
        return _session

    # Create + health-check, retrying session creation once on timeout-like errors.
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            s = curl_requests.Session(impersonate="chrome124")
            # Quick connectivity check (no need to download big pages)
            s.get(_BASE_URL, timeout=10)
            _session = s
            return _session
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if attempt == 0 and ("timed out" in msg or "timeout" in msg):
                time.sleep(0.1)
                continue
            break

    raise last_err if last_err is not None else RuntimeError("failed to create DART session. please retry.")


def _dart_get(url: str, **kwargs):
    """GET with curl_cffi session (browser TLS fingerprint)."""
    url = url.replace("http://dart.fss.or.kr", _BASE_URL)
    kwargs.setdefault("timeout", 30)

    # DART occasionally times out on the first attempt (transient network/TLS),
    # but succeeds immediately on retry. Retry once defensively.
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            return _get_session().get(url, **kwargs)
        except CurlCffiTimeout as e:
            last_err = e
            if attempt == 0:
                time.sleep(0.1)
                continue
            raise
        except Exception as e:
            # If curl_cffi surfaces timeouts as other exception types, still retry once
            # when the error clearly indicates a timeout.
            last_err = e
            msg = str(e).lower()
            if attempt == 0 and ("timed out" in msg or "timeout" in msg):
                time.sleep(0.1)
                continue
            raise

    # Unreachable, but keeps type-checkers happy.
    if last_err is not None:
        raise last_err
    raise RuntimeError("unexpected failure during session creation. please retry.")


def list_dart_disclosures_by_date(
    date: str,
    start_page: int = 1,
    end_page: int = 10,
) -> List[Dict[str, Any]]:
    """
    지정한 날짜에 공시된 모든 보고서 목록을 조회합니다. 특정 날짜에 어떤 기업들이 어떤 공시를 했는지 확인할 때 사용합니다.

    Args:
        date: 조회일. 문자열(YYYYMMDD, YYYY-MM-DD 등 `pandas.to_datetime`이 해석 가능한 형식)
        start_page: 조회 시작 페이지 (1부터 시작, 기본값 1).
        end_page: 조회 끝 페이지 (포함, 기본값 10).

    Returns:
        list[dict]: 공시 보고서 목록. 각 항목은 다음과 같은 키를 포함합니다:
            - rcept_dt (Timestamp): 접수일시 (예: Timestamp('2026-01-28 17:30:00'))
            - corp_cls (str): 법인구분 (예: '유', '코', '채', '넥' 등)
            - corp_name (str): 공시대상 회사명
            - rcept_no (str): 접수번호(14자리)
            - report_nm (str): 보고서명
            - flr_nm (str): 공시 제출인명
            - rm (str): 비고
    """
    if start_page > end_page:
        raise ValueError(f"start_page({start_page}) must be <= end_page({end_page})")

    date = pd.to_datetime(date) if date else datetime.today()
    date_str = date.strftime("%Y.%m.%d")

    columns = ["rcept_dt", "corp_cls", "corp_name", "rcept_no", "report_nm", "flr_nm", "rm"]

    df_list = []
    for page in range(start_page, end_page + 1):
        time.sleep(0.1)
        url = f"{_BASE_URL}/dsac001/search.ax?selectDate={date_str}&pageGrouping=A&currentPage={page}"
        xhtml_text = _dart_get(url).text

        if "검색된 자료가 없습니다" in xhtml_text:
            if page == start_page:
                return []
            break

        data_list = []
        soup = BeautifulSoup(xhtml_text, features="lxml")
        trs = soup.table.tbody.find_all("tr")
        for tr in trs:
            tds = tr.find_all("td")
            hhmm = tds[0].text.strip()
            corp_class = tds[1].span.span.text
            name = tds[1].span.a.text.strip()
            rcept_no = tds[2].a["href"].split("=")[1]
            title = " ".join(tds[2].a.text.split())
            fr_name = tds[3].text
            remark = "".join([span.text for span in tds[5].find_all("span")])
            dt = date.strftime("%Y-%m-%d") + " " + hhmm
            data_list.append([dt, corp_class, name, rcept_no, title, fr_name, remark])

        df = pd.DataFrame(data_list, columns=columns)
        df["rcept_dt"] = pd.to_datetime(df["rcept_dt"])
        df_list.append(df)

    if not df_list:
        return []

    merged = pd.concat(df_list).reset_index(drop=True)
    return merged.to_dict("records")


def get_dart_report_sub_documents(rcept_no: str, match: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    공시 문서 내부의 목차(하위 섹션) 목록을 조회합니다. 사업보고서와 같은 긴 문서에서 '재무제표', '사업의 내용' 등 특정 섹션의 URL을 찾을 때 사용합니다.

    Args:
        rcept_no: 접수번호(14자리. 예: 20190401004781) 또는 하위 문서를 포함한 DART URL (`http`로 시작).
        match: 매칭할 문자열. 지정하면 제목과의 유사도 기준으로 내림차순 정렬합니다.

    Returns:
        list[dict]: 하위 문서 목록. 각 항목은 다음 키를 포함합니다:
            - title (str): 문서 제목
            - url (str): 뷰어 URL
    """
    if rcept_no.isdecimal():
        r = _dart_get(f"{_BASE_URL}/dsaf001/main.do?rcpNo={rcept_no}")
    elif rcept_no.startswith("http"):
        r = _dart_get(rcept_no)
    else:
        raise ValueError("invalid `rcept_no`(or url)")

    # 하위 문서 URL 추출
    multi_page_re = (
        r"\s+node[12]\['text'\][ =]+\"(.*?)\"\;"
        r"\s+node[12]\['id'\][ =]+\"(\d+)\";"
        r"\s+node[12]\['rcpNo'\][ =]+\"(\d+)\";"
        r"\s+node[12]\['dcmNo'\][ =]+\"(\d+)\";"
        r"\s+node[12]\['eleId'\][ =]+\"(\d+)\";"
        r"\s+node[12]\['offset'\][ =]+\"(\d+)\";"
        r"\s+node[12]\['length'\][ =]+\"(\d+)\";"
        r"\s+node[12]\['dtd'\][ =]+\"(.*?)\";"
        r"\s+node[12]\['tocNo'\][ =]+\"(\d+)\";"
    )
    matches = re.findall(multi_page_re, r.text)
    if len(matches) > 0:
        row_list = []
        for m in matches:
            doc_title = m[0]
            params = f"rcpNo={m[2]}&dcmNo={m[3]}&eleId={m[4]}&offset={m[5]}&length={m[6]}&dtd={m[7]}"
            doc_url = f"{_BASE_URL}/report/viewer.do?{params}"
            row_list.append([doc_title, doc_url])
        df = pd.DataFrame(row_list, columns=["title", "url"])
        if match:
            df["similarity"] = df["title"].apply(lambda x: difflib.SequenceMatcher(None, x, match).ratio())
            df = df.sort_values("similarity", ascending=False)
        return df[["title", "url"]].to_dict("records")
    else:
        single_page_re = r"\t\tviewDoc\('(\d+)', '(\d+)', '(\d+)', '(\d+)', '(\d+)', '(\S+)',''\)\;"
        matches = re.findall(single_page_re, r.text)
        if len(matches) > 0:
            doc_title = BeautifulSoup(r.text, features="lxml").title.text.strip()
            m = matches[0]
            params = f"rcpNo={m[0]}&dcmNo={m[1]}&eleId={m[2]}&offset={m[3]}&length={m[4]}&dtd={m[5]}"
            doc_url = f"{_BASE_URL}/report/viewer.do?{params}"
            df_single = pd.DataFrame([[doc_title, doc_url]], columns=["title", "url"])
            return df_single.to_dict("records")
        else:
            raise Exception(f"{rcept_no} 하위 페이지를 포함하고 있지 않습니다")

    return []


def extract_dart_viewer_content(url: str) -> str:
    """
    DART viewer URL로부터 page content를 추출합니다.

    Args:
        url: DART viewer URL (e.g. http://dart.fss.or.kr/report/viewer.do?rcpNo=...)

    Returns:
        str: Viewer URL로부터 추출한 텍스트
    """
    try:
        response = _dart_get(url)
        response.raise_for_status()
        if hasattr(response, "apparent_encoding"):
            response.encoding = response.apparent_encoding
    except Exception as e:
        return f"Error: Request failed - {str(e)}"
    try:
        response = parse_dart_to_text(response.text, include_meta=False)
    except Exception:
        try:
            response = html_to_markdown_keep_tables(response.text)
        except Exception:
            response = response.text.strip()
    return response


def get_dart_report_attached_documents(rcept_no: str, match: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    공시에 첨부된 관련 공시 문서 목록을 조회합니다. 사업보고서에 첨부된 '정관', '감사보고서', '내부회계관리제도' 등의 다른 공시 페이지를 찾을 때 사용합니다.

    Args:
        rcept_no: 접수번호(14자리. 예: 20190401004781).
        match: 문서 제목과의 유사도 기준으로 정렬할 기준 문자열. 지정하면 유사도가 높은 순으로 정렬합니다.

    Returns:
        list[dict]: 첨부문서 목록. 각 항목은 다음 키를 포함합니다:
            - title (str): 첨부문서 제목
            - url (str): 첨부문서 메인 URL
    """
    r = _dart_get(f"{_BASE_URL}/dsaf001/main.do?rcpNo={rcept_no}")
    soup = BeautifulSoup(r.text, features="lxml")

    row_list = []
    att = soup.find(id="att")
    if not att:
        raise Exception(f"rcept_no={rcept_no} 첨부문서를 포함하고 있지 않습니다")

    for opt in att.find_all("option"):
        if opt["value"] == "null":
            continue
        title = " ".join(opt.text.split())
        url = f"{_BASE_URL}/dsaf001/main.do?{opt['value']}"
        row_list.append([title, url])

    df = pd.DataFrame(row_list, columns=["title", "url"])
    if match:
        df["similarity"] = df["title"].apply(lambda x: difflib.SequenceMatcher(None, x, match).ratio())
        df = df.sort_values("similarity", ascending=False)
    return df[["title", "url"]].to_dict("records")


def get_dart_report_downloadable_attachments(arg: str) -> Dict[str, str]:  # rcept_no 또는 URL
    """
    공시에 첨부된 실제 다운로드 가능한 파일(PDF, Excel, 한글 문서 등)의 목록과 다운로드 링크를 조회합니다.

    Args:
        arg: 접수번호(14자리. 예: 20190401004781) 또는 첨부문서 다운로드 페이지로 연결되는 URL(`http`로 시작).

    Returns:
        dict[str, str]: 첨부파일 이름을 키로, 다운로드 URL을 값으로 갖는 딕셔너리.
    """
    url = arg if arg.startswith("http") else f"{_BASE_URL}/dsaf001/main.do?rcpNo={arg}"
    r = _dart_get(url)

    rcept_no = dcm_no = None
    # Use raw string to avoid syntax warnings about escape sequences
    matches = re.findall(
        r"\s+node[12]\['rcpNo'\][ =]+\"(\d+)\";"
        r"\s+node[12]\['dcmNo'\][ =]+\"(\d+)\";",
        r.text,
    )
    if matches:
        rcept_no = matches[0][0]
        dcm_no = matches[0][1]

    if not dcm_no:
        print(f"{url} does not have download page. 다운로드 페이지를 포함하고 있지 않습니다.")

    download_url = f"{_BASE_URL}/pdf/download/main.do?rcp_no={rcept_no}&dcm_no={dcm_no}"
    r = _dart_get(download_url)
    soup = BeautifulSoup(r.text, features="lxml")
    table = soup.find("table")
    if not table:
        return {}

    attach_files_dict = {}
    for tr in table.tbody.find_all("tr"):
        tds = tr.find_all("td")
        fname = tds[0].text
        flink = _BASE_URL + tds[1].a["href"]
        attach_files_dict[fname] = flink
    return attach_files_dict


def download(url, fn=None):
    fn = fn if fn else url.split("/")[-1]
    r = _dart_get(url, stream=True)
    if r.status_code != 200:
        print(r.status_code)
        return None

    with open(fn, "wb") as f:
        for chunk in r.iter_content(chunk_size=4096):
            f.write(chunk) if chunk else None
    return fn
