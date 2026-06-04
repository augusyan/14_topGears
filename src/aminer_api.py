"""
AMiner Open API Toolkit
=======================
封装的 AMiner 开放数据平台 API, 用于学术文献检索与分析。

用法:
    from aminer_api import AMinerClient
    client = AMinerClient(token="your_jwt_token")
    papers = client.search_papers(title="knowledge graph", size=10)

API 端点列表:
    search_papers    论文搜索pro   0.01元/次
    paper_detail     论文详情      0.01元/次
    paper_info       论文信息      免费 (批量)
    paper_citations  论文引用      0.10元/次
    search_persons   学者搜索      免费
    person_detail    学者详情      1.00元/次
    org_detail       机构详情      0.01元/次
"""

import time
import requests
from typing import Optional

BASE_URL = "https://datacenter.aminer.cn/gateway/open_platform/api"


class AMinerClient:
    def __init__(self, token: str):
        self.token = token
        self._last_call = 0

    def _headers(self, content_type: Optional[str] = None) -> dict:
        h = {"Authorization": self.token}
        if content_type:
            h["Content-Type"] = content_type
        return h

    def _rate_limit(self):
        now = time.time()
        elapsed = now - self._last_call
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        self._last_call = time.time()

    # ========== Paper APIs ==========

    def search_papers(self, title: str = "", keyword: str = "",
                      abstract: str = "", author: str = "", org: str = "",
                      venue: str = "", order: str = "n_citation",
                      page: int = 0, size: int = 10) -> dict:
        """
        论文搜索 Pro (0.01元/次)
        order: "year" | "n_citation" (降序)
        size: max 100
        """
        self._rate_limit()
        url = f"{BASE_URL}/paper/search/pro"
        params = {k: v for k, v in {
            "page": page, "size": size, "title": title,
            "keyword": keyword, "abstract": abstract,
            "author": author, "org": org, "venue": venue,
            "order": order,
        }.items() if v}
        resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
        return resp.json()

    def paper_detail(self, paper_id: str) -> dict:
        """论文详情 (0.01元/次)"""
        self._rate_limit()
        url = f"{BASE_URL}/paper/detail"
        resp = requests.get(url, headers=self._headers(), params={"id": paper_id}, timeout=30)
        return resp.json()

    def paper_info(self, paper_ids: list[str]) -> dict:
        """论文信息 免费 (批量, 最多100个ID)"""
        self._rate_limit()
        url = f"{BASE_URL}/paper/info"
        resp = requests.post(url, headers=self._headers("application/json;charset=utf-8"),
                             json={"ids": paper_ids[:100]}, timeout=30)
        return resp.json()

    def paper_citations(self, paper_id: str) -> dict:
        """论文引用关系 (0.10元/次)"""
        self._rate_limit()
        url = f"{BASE_URL}/paper/relation"
        resp = requests.get(url, headers=self._headers(), params={"id": paper_id}, timeout=30)
        return resp.json()

    # ========== Person APIs ==========

    def search_persons(self, name: str = "", org: str = "",
                       org_id: list[str] = None, size: int = 10) -> dict:
        """学者搜索 免费 (max size=10)"""
        self._rate_limit()
        url = f"{BASE_URL}/person/search"
        body = {"size": size}
        if name:
            body["name"] = name
        if org:
            body["org"] = org
        if org_id:
            body["org_id"] = org_id
        resp = requests.post(url, headers=self._headers("application/json;charset=utf-8"),
                             json=body, timeout=30)
        return resp.json()

    def person_detail(self, person_id: str) -> dict:
        """学者详情 (1.00元/次)"""
        self._rate_limit()
        url = f"{BASE_URL}/person/detail"
        resp = requests.get(url, headers=self._headers(), params={"id": person_id}, timeout=30)
        return resp.json()

    # ========== Organization APIs ==========

    def org_detail(self, org_ids: list[str]) -> dict:
        """机构详情 (0.01元/次)"""
        self._rate_limit()
        url = f"{BASE_URL}/organization/detail"
        resp = requests.post(url, headers=self._headers("application/json;charset=utf-8"),
                             json={"ids": org_ids}, timeout=30)
        return resp.json()


# ========== 辅助函数 ==========

def extract_ids(response: dict) -> list[str]:
    """从搜索响应中提取 paper/person ID 列表"""
    data = response.get("data", [])
    if isinstance(data, list):
        return [item["id"] for item in data if "id" in item]
    return []


def fmt_paper(p: dict) -> str:
    """格式化单篇论文为一行"""
    title = (p.get("title") or p.get("title_zh", "?"))[:80]
    year = p.get("year", "?")
    venue = p.get("venue_name", p.get("raw", "?"))
    doi = p.get("doi", "")
    return f"[{year}] {title} | {venue} | {doi}"
