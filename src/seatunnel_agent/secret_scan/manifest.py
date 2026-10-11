# -*- coding: utf-8 -*-
"""Platform plugin manifest — see seatunnel_agent.registry."""

from ..registry import AgentManifest

MANIFEST = AgentManifest(
    name="secret_scan",
    workspace="devops",
    route="/secretscan",
    page_title="Secret Scan",
    logo="🔑",
    color="#dc2626",
    title_en="Secret Scan",
    title_zh="敏感凭证扫描",
    desc_en=("Provider tokens, private keys, password assignments & high-entropy strings — masked previews, CI gate"),
    desc_zh=("云厂商 token、私钥、明文密码与高熵串 — 预览脱敏,可做 CI 门禁"),
    render="seatunnel_agent.secret_scan_ui:render_secret_scan_page",
    api="seatunnel_agent.secret_scan.api:router",
    order=10,
)
