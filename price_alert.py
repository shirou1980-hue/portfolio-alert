name: Daily Portfolio & Dividend Alert

on:
  schedule:
    # UTC 20:00 = 한국 시간(KST) 매일 아침 05:00
    - cron: '0 20 * * *'
  workflow_dispatch:

jobs:
  run-alert:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install yfinance requests

      - name: Run Alert Script
        env:
          KAKAO_CLIENT_ID: ${{ secrets.KAKAO_CLIENT_ID }}
          KAKAO_REFRESH_TOKEN: ${{ secrets.KAKAO_REFRESH_TOKEN }}
          KAKAO_ACCESS_TOKEN: ${{ secrets.KAKAO_ACCESS_TOKEN }}
        run: python price_alert.py
