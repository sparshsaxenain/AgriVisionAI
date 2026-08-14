"""Reusable visual components and agriculture-themed styling."""
from __future__ import annotations

import html

import streamlit as st


def apply_theme() -> None:
    st.markdown("""
    <style>
      :root { --leaf:#247a45; --leaf-dark:#155f32; --soil:#8b5e3c; --cream:#f7f7f1; }
      .stApp { background: linear-gradient(180deg,#fbfcf8 0%,#f4f7f0 100%); }
      [data-testid="stSidebar"] { background:#173d2a; }
      [data-testid="stSidebar"] * { color:#f6fbf7 !important; }
      [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] * { color:#173d2a !important; }
      .block-container { max-width:1200px; padding-top:1.6rem; }
      h1,h2,h3 { color:#173d2a; letter-spacing:-0.02em; }
      .stButton>button, .stFormSubmitButton>button { min-height:3rem; border-radius:12px; font-weight:700; border:0; background:#247a45; color:white; }
      .stButton>button:hover, .stFormSubmitButton>button:hover { background:#155f32; color:white; }
      div[data-testid="stMetric"] { background:white; border:1px solid #e2eadf; padding:1rem; border-radius:16px; box-shadow:0 3px 12px rgba(23,61,42,.06); }
      .ag-card { background:white; border:1px solid #e2eadf; padding:1rem 1.1rem; border-radius:16px; margin:.4rem 0 1rem; box-shadow:0 3px 12px rgba(23,61,42,.06); }
      .ag-eyebrow { color:#247a45; text-transform:uppercase; font-size:.75rem; font-weight:800; letter-spacing:.08em; }
      .ag-muted { color:#637269; font-size:.9rem; }
      .ag-chip { display:inline-block; border-radius:999px; padding:.25rem .65rem; font-weight:800; font-size:.76rem; background:#e8f4eb; color:#155f32; }
      .ag-chip.warning { background:#fff3cf; color:#7a5300; } .ag-chip.critical { background:#ffe3df; color:#a32920; }
      @media(max-width:700px){ .block-container{padding:.8rem .75rem 4rem;} h1{font-size:1.75rem;} }
    </style>
    """, unsafe_allow_html=True)


def page_title(title: str, subtitle: str) -> None:
    st.markdown(f"<div class='ag-eyebrow'>AgriVision AI</div><h1 style='margin:.15rem 0'>{html.escape(title)}</h1><p class='ag-muted'>{html.escape(subtitle)}</p>", unsafe_allow_html=True)


def card(title: str, body: str, chip: str = "", severity: str = "") -> None:
    chip_html = f"<span class='ag-chip {html.escape(severity)}'>{html.escape(chip)}</span>" if chip else ""
    st.markdown(f"<div class='ag-card'>{chip_html}<h3 style='margin:.55rem 0 .25rem'>{html.escape(title)}</h3><div class='ag-muted'>{html.escape(body)}</div></div>", unsafe_allow_html=True)


def api_error(exc: Exception) -> None:
    st.error(str(exc), icon="⚠️")

