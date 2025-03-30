import aiohttp
import json
from pathlib import Path
from fake_useragent import UserAgent
from yarl import URL


class BrowserClient:
    def __init__(self, username: str, proxy: str = None, storage_dir="sessions"):
        self.username = username
        self.proxy = proxy
        self.storage_path = Path(storage_dir)
        self.cookies_path = self.storage_path / f"{username}_cookies.pkl"
        self.ua_path = self.storage_path / f"{username}_ua.txt"
        self.meta_path = self.storage_path / f"{username}_meta.json"

        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.cookie_jar = aiohttp.CookieJar()
        self._load_cookies()
        self.user_agent = self._load_or_generate_user_agent()
        self.meta = self._load_meta()

        connector = aiohttp.TCPConnector(ssl=False)

        self.session = aiohttp.ClientSession(
            cookie_jar=self.cookie_jar,
            headers={"User-Agent": self.user_agent},
            connector=connector
        )

    async def request(self, url: str, method: str = "GET", **kwargs) -> any:
        if self.proxy:
            kwargs["proxy"] = self.proxy

        if "timeout" not in kwargs:
            kwargs["timeout"] = aiohttp.ClientTimeout(total=60)

        async with self.session.request(method=method, url=url, **kwargs) as response:
            #response.raise_for_status()
            result = {'response': response}
            if response.content_type == "application/json":
                result['data'] = await response.json()
            else:
                result['data'] = await response.text()
            return result

    def save(self):
        self._save_cookies()
        self._save_meta()

    async def close(self):
        self._save_cookies()
        self._save_meta()
        await self.session.close()

    def _load_or_generate_user_agent(self) -> str:
        if self.ua_path.exists():
            return self.ua_path.read_text().strip()
        else:
            ua = UserAgent().random
            self.ua_path.write_text(ua)
            return ua

    def _load_cookies(self):
        if not self.cookies_path.exists():
            return

        try:
            with open(self.cookies_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
                for c in cookies:
                    self.cookie_jar.update_cookies(
                        {c["key"]: c["value"]},
                        response_url=URL(f"https://{c['domain']}")
                    )
        except Exception:
            pass

    def _save_cookies(self):
        cookies = []
        for cookie in self.cookie_jar:
            cookies.append({
                "key": cookie.key,
                "value": cookie.value,
                "domain": cookie["domain"],
                "path": cookie["path"],
                "secure": cookie["secure"],
                "expires": cookie["expires"],
            })
        with open(self.cookies_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2)

    def _load_meta(self):
        if self.meta_path.exists():
            try:
                with open(self.meta_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_meta(self):
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(self.meta, f, indent=2)

    def set_param(self, key, value):
        self.meta[key] = value
        self._save_meta()

    def get_param(self, key, default=None):
        return self.meta.get(key, default)

    def del_param(self, key):
        if key in self.meta:
            del self.meta[key]
            self._save_meta()
