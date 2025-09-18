import streamlit as st
import pandas as pd
import json
import os
import glob
from pathlib import Path
from datetime import datetime

# 페이지 설정
st.set_page_config(
    page_title="Data Quality Report Dashboard",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 스타일링
st.markdown("""
<style>
.issue-card {
    background-color: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 15px;
    margin: 10px 0;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
.match-success { color: #28a745; font-weight: bold; }
.match-error { color: #dc3545; font-weight: bold; }
.match-warning { color: #ffc107; font-weight: bold; }
.editable-cell { background-color: #fff3cd; padding: 2px 8px; border-radius: 4px; }
.report-header {
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 20px;
    border-radius: 10px;
    text-align: center;
    margin-bottom: 20px;
}
</style>
""", unsafe_allow_html=True)

all_fields_mapping = {
    # Income Statement 항목들
    'totalRevenue': {'section': 'Income_Statement', 'display': 'Total Revenue', 'yf_key': 'Total Revenue'},
    'netIncome': {'section': 'Income_Statement', 'display': 'Net Income', 'yf_key': 'Net Income'},
    'grossProfit': {'section': 'Income_Statement', 'display': 'Gross Profit', 'yf_key': 'Gross Profit'},
    'operatingIncome': {'section': 'Income_Statement', 'display': 'Operating Income', 'yf_key': 'Operating Income'},
    'incomeBeforeTax': {'section': 'Income_Statement', 'display': 'Pretax Income', 'yf_key': 'Pretax Income'},
    'ebitda': {'section': 'Income_Statement', 'display': 'EBITDA', 'yf_key': 'Normalized EBITDA'},

    # Balance Sheet 항목들
    'totalAssets': {'section': 'Balance_Sheet', 'display': 'Total Assets', 'yf_key': 'Total Assets'},
    'totalLiab': {'section': 'Balance_Sheet', 'display': 'Total Liabilities',
                  'yf_key': 'Total Liabilities Net Minority Interest'},
    'totalStockholderEquity': {'section': 'Balance_Sheet', 'display': 'Total Equity',
                               'yf_key': 'Total Equity Gross Minority Interest'},
    'netDebt': {'section': 'Balance_Sheet', 'display': 'Net Debt', 'yf_key': 'Net Debt'},

    # Cash Flow 항목들
    'totalCashFromOperatingActivities': {'section': 'Cash_Flow', 'display': 'Operating Cash Flow',
                                         'yf_key': 'Operating Cash Flow'},
    'totalCashflowsFromInvestingActivities': {'section': 'Cash_Flow', 'display': 'Investing Cash Flow',
                                              'yf_key': 'Investing Cash Flow'},
    'totalCashFromFinancingActivities': {'section': 'Cash_Flow', 'display': 'Financing Cash Flow',
                                         'yf_key': 'Financing Cash Flow'},
    'freeCashFlow': {'section': 'Cash_Flow', 'display': 'Free Cash Flow', 'yf_key': 'Free Cash Flow'},
}

def get_mapped_value(df, mapping, provider="yf"):
    key = mapping.get(f"{provider}_key")
    if key and key in df.columns:
        return df[key]
    else:
        return None



class IssueTracker:
    def __init__(self):
        self.issues_file = "data_issues.json"
        self.load_issues()

    def load_issues(self):
        """저장된 이슈 로드"""
        if os.path.exists(self.issues_file):
            try:
                with open(self.issues_file, 'r', encoding='utf-8') as f:
                    self.issues = json.load(f)
            except json.JSONDecodeError:
                self.issues = {}
        else:
            self.issues = {}

    def save_issues(self):
        """이슈 저장"""
        with open(self.issues_file, 'w', encoding='utf-8') as f:
            json.dump(self.issues, f, ensure_ascii=False, indent=2)

    def add_issue(self, ticker, field, issue_data):
        """이슈 추가/업데이트"""
        if ticker not in self.issues:
            self.issues[ticker] = {}

        issue_key = f"{field}_{issue_data.get('date', 'general')}"
        self.issues[ticker][issue_key] = {
            **issue_data,
            'updated_at': datetime.now().isoformat(),
            'status': issue_data.get('status', 'open')
        }
        self.save_issues()

    def get_issues(self, ticker=None):
        """이슈 조회"""
        if ticker:
            return self.issues.get(ticker, {})
        return self.issues


class DataComparator:
    def __init__(self):
        self.eodhd_dir = './data'
        self.yfinance_dir = './yfinance_data'
        self.issue_tracker = IssueTracker()

        self.exchange_mapping = {
            'United States-NASDAQ': 'US',
            'United States-New York Stock Exchange Inc.': 'US',
            'Netherlands-Euronext Amsterdam': 'AS',
            'Germany-Xetra': 'XETRA',
            'United Kingdom-London Stock Exchange': 'LSE',
            'Switzerland-SIX Swiss Exchange': 'SW',
            'Canada-Toronto Stock Exchange': 'TO',
            'Japan-Tokyo Stock Exchange': 'JP',
            'Denmark-Omx Nordic Exchange Copenhagen A/S': 'CO',
            'Australia-Asx - All Markets': 'AU',
            'France-Nyse Euronext - Euronext Paris': 'PA',
            'Spain-Bolsa De Madrid': 'MC',
            'Belgium-Nyse Euronext - Euronext Brussels': 'BR',
            'Singapore-Singapore Exchange': 'SG',
            'Israel-Tel Aviv Stock Exchange': 'TA',
            'Norway-Oslo Bors Asa': 'OL',
            'New Zealand-New Zealand Exchange Ltd': 'NZ',
            'Italy-Borsa Italiana': 'MI',
            'Portugal-Nyse Euronext - Euronext Lisbon': 'LS',
            'Sweden-Nasdaq Omx Nordic': 'ST',
            'Hong Kong-Hong Kong Exchanges And Clearing Ltd': 'HK',
            'Austria-Wiener Boerse Ag': 'VI',
        }

        # 일반적인 차이 원인들
        self.common_causes = [
            "소수점 반올림 차이",
            "데이터 제공 시점 차이",
            "조정 계산 방식 차이",
            "거래소별 데이터 처리 차이",
            "환율 적용 차이",
            "분할/배당 조정 차이",
            "데이터 소스 차이",
            "시간대 차이",
            "기타"
        ]

    def get_ticker_list(self):
        """CSV에서 티커 목록 추출"""
        try:
            df = pd.read_csv('URTH_holdings_edit.csv')
            equity_df = df[df['Asset Class'] == 'Equity']
            equity_df['Weight (%)'] = equity_df['Weight (%)'].astype(float)
            top_stocks = equity_df.groupby('Exchange').apply(
                lambda x: x.nlargest(1, 'Weight (%)')
            ).reset_index(drop=True)

            full_tickers = []
            for _, row in top_stocks.iterrows():
                key = f"{row['Location']}-{row['Exchange']}"
                code = self.exchange_mapping.get(key, None)
                if code:
                    full_ticker = f"{row['Ticker']}.{code}"
                    full_tickers.append((full_ticker, row['Exchange'], row['Location']))

            # 특정 티커 추가
            specific_tickers = []
            for ticker in specific_tickers:
                if (ticker, 'NASDAQ or NYSE', 'United States') not in full_tickers:
                    full_tickers.append((ticker, 'NASDAQ or NYSE' if '.US' in ticker else 'HKG',
                                         'United States' if '.US' in ticker else 'Hong Kong'))

            return sorted(full_tickers, key=lambda x: x[0])
        except Exception as e:
            st.error(f"티커 목록 로드 오류: {e}")
            return []

    def load_data(self, ticker, data_type, source='both'):
        """데이터 로드"""
        results = {}

        eodhd_ticker = ticker
        yf_ticker = ticker.replace('.US', '') if '.US' in ticker else ticker
        yf_ticker = yf_ticker.replace('.LSE', '.L') if '.LSE' in yf_ticker else yf_ticker

        if source in ['both', 'eodhd']:
            eodhd_file = self._get_file_path('eodhd', eodhd_ticker, data_type)
            if os.path.exists(eodhd_file):
                results['eodhd'] = self._load_file(eodhd_file, data_type)

        if source in ['both', 'yfinance']:
            yf_file = self._get_file_path('yfinance', yf_ticker, data_type)
            if os.path.exists(yf_file):
                results['yfinance'] = self._load_file(yf_file, data_type)

        return results

    def _get_file_path(self, source, ticker, data_type):
        """파일 경로 생성"""
        base_dir = self.eodhd_dir if source == 'eodhd' else self.yfinance_dir

        # 파일명 매핑
        if source == 'eodhd':
            file_names = {
                'income_statement': f'income_statement_{ticker}.json',
                'balance_sheet': f'balance_sheet_{ticker}.json',
                'cash_flow': f'cash_flow_{ticker}.json',
                'historical_ohlc': f'historical_ohlc_{ticker}.csv',
                'dividends': f'dividends_{ticker}.csv',
                'fundamentals': f'fundamentals_{ticker}.json'
            }
        else:
            file_names = {
                'income_statement': f'income_statement_{ticker}.csv',
                'balance_sheet': f'balance_sheet_{ticker}.csv',
                'cash_flow': f'cash_flow_{ticker}.csv',
                'historical_ohlc': f'historical_ohlc_{ticker}.csv',
                'dividends': f'dividends_{ticker}.csv',
                'fundamentals': f'fundamentals_{ticker}.json'
            }

        file_name = file_names.get(data_type)
        if not file_name:
            # 기본값으로 티커 파일명 사용
            file_name = f'data_{ticker}.json'

        return os.path.join(base_dir, file_name)

    def _load_file(self, file_path, data_type):
        """파일 로드"""
        try:
            if file_path.endswith('.csv'):
                return pd.read_csv(file_path)
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            st.error(f"파일 로드 오류 ({file_path}): {e}")
            return None

    def get_ohlc_compare_data(self, eodhd_df, yf_df, num_records, ticker, order_type: str = 'ascending') -> list:

        comparison_results = []

        # 💡 EODHD 데이터에 Adjusted_close 값이 있는 경우, OHLC 값을 수정주가로 변환합니다.
        if 'adjusted_close' in eodhd_df.columns:
            eodhd_df['split_factor'] = eodhd_df['close'] / eodhd_df['adjusted_close']
            eodhd_df['open'] = eodhd_df['open'] / eodhd_df['split_factor']
            eodhd_df['high'] = eodhd_df['high'] / eodhd_df['split_factor']
            eodhd_df['low'] = eodhd_df['low'] / eodhd_df['split_factor']
            eodhd_df['close'] = eodhd_df['close'] / eodhd_df['split_factor']

        filter_eodhd_df = pd.DataFrame()
        filter_yf_df = pd.DataFrame()

        if order_type == 'ascending':
            # yfinance 기준으로 초기 날짜 num_records 개 추출
            filter_yf_df = yf_df.sort_values('Date', ascending=True).head(num_records)

            # yfinance에서 추출한 날짜 리스트를 사용하여 EODHD 데이터 필터링
            yf_dates = filter_yf_df['Date'].tolist()
            filter_eodhd_df = eodhd_df[eodhd_df['Date'].isin(yf_dates)]

        else:
            filter_eodhd_df = eodhd_df.sort_values('Date', ascending=False).head(num_records)
            filter_yf_df = yf_df.sort_values('Date', ascending=False).head(num_records)

        for _, eodhd_row in filter_eodhd_df.iterrows():
            date_str = eodhd_row['Date'].strftime('%Y-%m-%d')

            yf_row = filter_yf_df[filter_yf_df['Date'].dt.strftime('%Y-%m-%d') == date_str]

            if yf_row.empty: continue
            yf_row = yf_row.iloc[0]

            fields_to_compare = ['Open', 'High', 'Low', 'Close', 'Volume']
            for field in fields_to_compare:
                eodhd_field = field.lower() if field.lower() in eodhd_row else field
                yf_field = field

                if eodhd_field in eodhd_row and yf_field in yf_row:
                    eodhd_val = eodhd_row[eodhd_field]
                    yf_val = yf_row[yf_field]
                    match_result, difference = self._detailed_compare(eodhd_val, yf_val, field)

                    existing_issues = self.issue_tracker.get_issues(ticker)
                    issue_key = f"{field}_{date_str}"
                    existing_cause = existing_issues.get(issue_key, {}).get('cause', '')

                    comparison_results.append({
                        'date': date_str, 'field': field, 'eodhd_value': self._format_value(eodhd_val, field),
                        'yfinance_value': self._format_value(yf_val, field), 'match': match_result,
                        'difference': difference, 'existing_cause': existing_cause, 'ticker': ticker
                    })

        return comparison_results

    def compare_detailed_data(self, ticker, data_type='historical_ohlc', num_records=10):
        """상세 데이터 비교 (보고서용)"""
        data = self.load_data(ticker, data_type)

        if 'eodhd' not in data or 'yfinance' not in data:
            return None, "데이터 로드 실패: EODHD 또는 yfinance 파일이 없습니다."

        eodhd_data = data['eodhd']
        yf_data = data['yfinance']

        if eodhd_data is None or yf_data is None:
            return None, "데이터 없음: 파일은 존재하나 내용이 비어있습니다."

        comparison_results = []

        if data_type == 'historical_ohlc':
            eodhd_df = eodhd_data.copy()
            yf_df = yf_data.copy()

            # EODHD 데이터: 'date' 또는 'Date' 열을 찾아 datetime 타입으로 변환
            if 'date' in eodhd_df.columns:
                eodhd_df['Date'] = pd.to_datetime(eodhd_df['date'], errors='coerce')
            elif 'Date' in eodhd_df.columns:
                eodhd_df['Date'] = pd.to_datetime(eodhd_df['Date'], errors='coerce')
            else:
                return None, "EODHD 데이터에 'date' 또는 'Date' 열이 없습니다."

            # yfinance 데이터: 'Date' 열의 문자열에서 시간대 정보를 제거 후 datetime으로 변환
            if 'Date' in yf_df.columns:
                # 💡 최종 해결책: 공백을 기준으로 문자열을 분리하여 날짜 부분만 추출
                yf_df['Date'] = yf_df['Date'].astype(str).str.split().str[0]
                yf_df['Date'] = pd.to_datetime(yf_df['Date'], errors='coerce')

                # 유효하지 않은 날짜(NaT)가 있는 행 제거
                yf_df = yf_df.dropna(subset=['Date'])
            else:
                return None, "yfinance 데이터에 'Date' 열이 없습니다."

            # 두 데이터프레임의 날짜 형식을 'yyyy-mm-dd'로 통일 (시간 정보 제거)
            eodhd_df['Date'] = eodhd_df['Date'].dt.normalize()
            yf_df['Date'] = yf_df['Date'].dt.normalize()

            eodhd_df = eodhd_df.dropna(subset=['Date'])
            result1 = self.get_ohlc_compare_data(eodhd_df=eodhd_df, yf_df=yf_df, num_records=num_records, ticker=ticker,
                                                 order_type='ascending')
            result2 = self.get_ohlc_compare_data(eodhd_df=eodhd_df, yf_df=yf_df, num_records=num_records, ticker=ticker,
                                                 order_type='descending')

            comparison_results = result1 + result2

        elif data_type == 'dividends':
            # 데이터 복사본 생성
            eodhd_df = eodhd_data.copy()
            yf_df = yf_data.copy()

            # yfinance 데이터 처리
            if 'Date' in yf_df.columns:
                # 시간대 정보가 포함된 날짜 문자열에서 날짜 부분만 추출
                yf_df['Date'] = yf_df['Date'].astype(str).str.split().str[0]
                yf_df['Date'] = pd.to_datetime(yf_df['Date'], errors='coerce')
                yf_df = yf_df.dropna(subset=['Date'])
            else:
                return None, "yfinance 데이터에 'Date' 열이 없습니다."

            # EODHD 데이터 처리
            if 'date' in eodhd_df.columns:
                eodhd_df['Date'] = pd.to_datetime(eodhd_df['date'], errors='coerce')
                eodhd_df = eodhd_df.dropna(subset=['Date'])
            elif 'Date' in eodhd_df.columns:
                eodhd_df['Date'] = pd.to_datetime(eodhd_df['Date'], errors='coerce')
                eodhd_df = eodhd_df.dropna(subset=['Date'])
            else:
                return None, "EODHD 데이터에 'date' 또는 'Date' 열이 없습니다."

            # 날짜 형식 통일 (시간 정보 제거)
            yf_df['Date'] = yf_df['Date'].dt.normalize()
            eodhd_df['Date'] = eodhd_df['Date'].dt.normalize()

            # 필요한 경우 배당 필드명 통일
            if 'Dividends' not in yf_df.columns and 'dividends' in yf_df.columns:
                yf_df['Dividends'] = yf_df['dividends']

            if 'value' in eodhd_df.columns:
                eodhd_df['dividend'] = eodhd_df['value']
            elif 'dividend' not in eodhd_df.columns:
                return None, "EODHD 데이터에 배당 금액 필드('value' 또는 'dividend')가 없습니다."

            # 데이터 정렬 (최신 순으로)
            yf_df = yf_df.sort_values('Date', ascending=False)
            eodhd_df = eodhd_df.sort_values('Date', ascending=False)

            # 최근 num_records 개로 제한
            if num_records:
                yf_df = yf_df.head(num_records)
                eodhd_df = eodhd_df.head(num_records)

            comparison_results = []

            # 각 데이터프레임을 순회하면서 공통 날짜 찾아서 비교
            for _, yf_row in yf_df.iterrows():
                yf_date = yf_row['Date']

                # 같은 날짜의 EODHD 데이터 찾기
                eodhd_match = eodhd_df[eodhd_df['Date'] == yf_date]

                if not eodhd_match.empty:
                    eodhd_row = eodhd_match.iloc[0]
                    date_str = yf_date.strftime('%Y-%m-%d')

                    # 배당금액 비교
                    field = 'Dividends'
                    yf_val = yf_row['Dividends'] if 'Dividends' in yf_row else 0
                    eodhd_val = eodhd_row['dividend'] if 'dividend' in eodhd_row else 0

                    match_result, difference = self._detailed_compare(eodhd_val, yf_val, 'dividend')

                    existing_issues = self.issue_tracker.get_issues(ticker)
                    issue_key = f"{field}_{date_str}"
                    existing_cause = existing_issues.get(issue_key, {}).get('cause', '')

                    comparison_results.append({
                        'date': date_str,
                        'field': field,
                        'eodhd_value': self._format_value(eodhd_val, 'dividend'),
                        'yfinance_value': self._format_value(yf_val, 'dividend'),
                        'match': match_result,
                        'difference': difference,
                        'existing_cause': existing_cause,
                        'ticker': ticker
                    })


        elif data_type == 'fundamentals':

            # EODHD 데이터에서 최신 재무년월 기준 데이터 추출

            eodhd_financials = {}

            latest_financial_date = None

            # Income Statement, Balance Sheet, Cash Flow에서 최신 재무년월 찾기

            financial_sections = ['Income_Statement', 'Balance_Sheet', 'Cash_Flow']

            for section in financial_sections:

                if section in eodhd_data.get('Financials', {}):

                    quarterly_data = eodhd_data['Financials'][section].get('quarterly', {})

                    if quarterly_data:

                        # 최신 재무년월 찾기

                        latest_date = max(quarterly_data.keys())

                        if latest_financial_date is None or latest_date > latest_financial_date:
                            latest_financial_date = latest_date

                        # 해당 섹션의 최신 데이터 저장

                        eodhd_financials[section] = quarterly_data[latest_date]

            if not eodhd_financials or not latest_financial_date:
                return None, "EODHD 데이터에 분기별 재무 데이터가 없습니다."

            # yfinance 데이터를 각 CSV 파일에서 로드

            yf_financials = {}

            financial_file_mapping = {

                'income_statement': 'Income_Statement',

                'balance_sheet': 'Balance_Sheet',

                'cash_flow': 'Cash_Flow'

            }

            for file_type, section in financial_file_mapping.items():

                yf_data_section = self.load_data(ticker, file_type, source='yfinance').get('yfinance')

                if yf_data_section is not None:

                    # CSV의 첫 번째 데이터 컬럼(최신)을 사용

                    if len(yf_data_section.columns) > 1:
                        # 첫 번째 컬럼은 'index', 두 번째부터가 실제 데이터

                        latest_column = yf_data_section.columns[1]

                        # index 컬럼을 행 이름으로 설정하고 최신 분기 데이터만 추출

                        yf_section_data = yf_data_section.set_index('index')[latest_column].to_dict()

                        yf_financials[section] = yf_section_data

            if not yf_financials:
                return None, "yfinance 재무제표 파일을 로드할 수 없습니다."

            # 비교할 필드 매핑 (EODHD 필드명 -> yfinance 행 이름)

            fields_mapping = {

                # Income Statement 항목들

                'totalRevenue': {'section': 'Income_Statement', 'display': 'Total Revenue', 'yf_key': 'Total Revenue'},

                'netIncome': {'section': 'Income_Statement', 'display': 'Net Income', 'yf_key': 'Net Income'},

                'grossProfit': {'section': 'Income_Statement', 'display': 'Gross Profit', 'yf_key': 'Gross Profit'},

                'operatingIncome': {'section': 'Income_Statement', 'display': 'Operating Income',
                                    'yf_key': 'Operating Income'},

                'incomeBeforeTax': {'section': 'Income_Statement', 'display': 'Pretax Income',
                                    'yf_key': 'Pretax Income'},

                'ebitda': {'section': 'Income_Statement', 'display': 'EBITDA', 'yf_key': 'Normalized EBITDA'},

                # Balance Sheet 항목들

                'totalAssets': {'section': 'Balance_Sheet', 'display': 'Total Assets', 'yf_key': 'Total Assets'},

                'totalLiab': {'section': 'Balance_Sheet', 'display': 'Total Liabilities',
                              'yf_key': 'Total Liabilities Net Minority Interest'},

                'totalStockholderEquity': {'section': 'Balance_Sheet', 'display': 'Total Equity',
                                           'yf_key': 'Total Equity Gross Minority Interest'},

                'netDebt': {'section': 'Balance_Sheet', 'display': 'Net Debt', 'yf_key': 'Net Debt'},

                # Cash Flow 항목들

                'totalCashFromOperatingActivities': {'section': 'Cash_Flow', 'display': 'Operating Cash Flow',
                                                     'yf_key': 'Operating Cash Flow'},

                'totalCashflowsFromInvestingActivities': {'section': 'Cash_Flow', 'display': 'Investing Cash Flow',
                                                          'yf_key': 'Investing Cash Flow'},

                'totalCashFromFinancingActivities': {'section': 'Cash_Flow', 'display': 'Financing Cash Flow',
                                                     'yf_key': 'Financing Cash Flow'},

                'freeCashFlow': {'section': 'Cash_Flow', 'display': 'Free Cash Flow', 'yf_key': 'Free Cash Flow'},

            }

            for eodhd_field, field_info in fields_mapping.items():

                section = field_info['section']

                display_field = field_info['display']

                yf_key = field_info['yf_key']

                # EODHD에서 해당 섹션의 필드 값 가져오기

                eodhd_val = None

                if section in eodhd_financials and eodhd_field in eodhd_financials[section]:

                    eodhd_val = eodhd_financials[section][eodhd_field]

                    # 문자열인 경우 숫자로 변환 시도

                    if isinstance(eodhd_val, str):

                        try:

                            eodhd_val = float(eodhd_val.replace(',', ''))

                        except (ValueError, AttributeError):

                            eodhd_val = None

                # yfinance에서 값 가져오기 (CSV 행 이름으로 접근)

                yf_val = None

                if section in yf_financials:

                    # yfinance CSV에서 해당 행의 값 찾기 (대소문자 구분 없이)

                    for row_name, value in yf_financials[section].items():

                        if yf_key.lower() in row_name.lower() or row_name.lower() in yf_key.lower():

                            try:

                                yf_val = float(value) if pd.notna(value) else None

                                break

                            except (ValueError, TypeError):

                                continue

                # 둘 다 값이 있는 경우에만 비교

                if eodhd_val is not None and yf_val is not None:
                    match_result, difference = self._detailed_compare(eodhd_val, yf_val, 'financial')

                    existing_issues = self.issue_tracker.get_issues(ticker)

                    issue_key = f"fundamentals_{eodhd_field}_{latest_financial_date}"

                    existing_cause = existing_issues.get(issue_key, {}).get('cause', '')

                    comparison_results.append({

                        'date': latest_financial_date,

                        'field': f"{display_field} ({section.replace('_', ' ')})",

                        'eodhd_value': self._format_value(eodhd_val, 'financial'),

                        'yfinance_value': self._format_value(yf_val, 'financial'),

                        'match': match_result,

                        'difference': difference,

                        'existing_cause': existing_cause,

                        'ticker': ticker

                    })

        return comparison_results, None

    def _detailed_compare(self, val1, val2, field_type):
        """상세 비교"""
        try:
            num1 = float(val1) if val1 != '' and pd.notna(val1) else 0
            num2 = float(val2) if val2 != '' and pd.notna(val2) else 0

            difference = abs(num1 - num2)

            # 필드 타입별 허용 오차
            if field_type in ['financial']:
                # 재무 데이터는 수치가 크므로 1000 단위까지 허용
                tolerance_abs = 1000
                if difference <= tolerance_abs:
                    return '✅', 0
                else:
                    return '❌', int(difference)
            elif field_type == 'Volume':
                tolerance_abs = 1
                if difference <= tolerance_abs:
                    return '✅', 0
                else:
                    return '❌', int(difference)
            elif field_type == 'dividend':
                if difference <= 0.001:
                    return '✅', 0
                else:
                    return '⚠️', round(difference, 4)
            else:  # 가격 데이터 (OHLC)
                percentage_diff = (difference / max(abs(num1), abs(num2), 0.01)) * 100
                if difference <= 0.01:
                    return '✅', 0
                elif percentage_diff <= 0.1:
                    return '⚠️', round(difference, 4)
                else:
                    return '❌', round(difference, 4)

        except (ValueError, TypeError):
            if str(val1) == str(val2):
                return '✅', 0
            else:
                return '❌', f"Type mismatch: {type(val1).__name__} vs {type(val2).__name__}"

    def _format_value(self, value, field_type):
        """값 포맷팅"""
        try:
            if field_type in ['Volume', 'financial', 'dividend']:
                return f"{float(value):,.4f}" if value != '' and pd.notna(value) else '0'
            else:
                return f"{float(value):.2f}" if value != '' and pd.notna(value) else '0.00'
        except:
            return str(value)


def extract_tickers_from_files(directory):
    """
    지정된 디렉토리의 파일 이름에서 종목 코드를 추출하고 중복을 제거합니다.
    파일 이름은 '파일명_종목코드.json' 형식을 따릅니다.
    """
    tickers = set()
    data_path = Path(directory)

    # 디렉토리가 존재하는지 확인
    if not data_path.exists():
        print(f"오류: 디렉토리 '{directory}'가 존재하지 않습니다.")
        return []

    # '.json' 확장자를 가진 모든 파일을 찾음
    file_list = glob.glob(str(data_path / "*.json"))

    if not file_list:
        print("경고: 지정된 디렉토리에서 .json 파일을 찾을 수 없습니다.")
        return []

    for file_path in file_list:
        file_name = os.path.basename(file_path)

        # 파일 이름에서 첫 번째 '_'와 확장자 사이의 문자열을 추출
        try:
            # ex: 'fundamentals_1299.HK.json' -> '1299.HK.json'
            ticker_with_ext = file_name.split('_', 1)[1]

            # ex: '1299.HK.json' -> '1299.HK'
            ticker = os.path.splitext(ticker_with_ext)[0]

            tickers.add(ticker)
        except IndexError:
            # 파일 이름에 '_'가 없는 경우 건너뛰기
            continue

    return sorted(list(tickers))


def main():

    st.markdown("""
    <div class="report-header">
        <h1>📋 Data Quality Assurance Report</h1>
        <p>데이터 품질 검증 및 이슈 트래킹 시스템</p>
    </div>
    """, unsafe_allow_html=True)

    comparator = DataComparator()
    ticker_list = comparator.get_ticker_list()

    if not ticker_list:
        st.error("티커 목록을 로드할 수 없습니다.")
        return

    # 사이드바 설정
    st.sidebar.header("📊 검증 설정")
    selected_ticker = st.sidebar.selectbox(
        "검증할 종목:",
        options=[ticker[0] for ticker in ticker_list],
        format_func=lambda x: f"{x} ({[t for t in ticker_list if t[0] == x][0][1]})"
    )

    data_type = st.sidebar.selectbox("데이터 유형:",
                                     ["historical_ohlc", "dividends", "financial_statements"])

    if data_type in ['historical_ohlc', 'dividends']:
        num_records = st.sidebar.slider("검증할 데이터 수", min_value=5, max_value=30, value=10)
    else:
        num_records = None

    # 메인 컨텐츠
    ticker_info = [t for t in ticker_list if t[0] == selected_ticker][0]

    st.header(f"📈 {selected_ticker} 데이터 품질 검증")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"**거래소**: {ticker_info[1]}")
    with col2:
        st.info(f"**지역**: {ticker_info[2]}")
    with col3:
        st.info(f"**검증 기준일**: {datetime.now().strftime('%Y-%m-%d')}")

    # 선택된 데이터 유형에 따라 다른 컨텐츠를 표시
    if data_type == "financial_statements":
        # 재무 데이터 상세 비교 섹션
        st.subheader("📋 재무 데이터 상세 비교")

        # 펀더멘탈 파일에서 업종/섹터 정보 로드
        try:
            with open(f"./yfinance_data/fundamentals_{selected_ticker.replace('.US', '')}.json", 'r',
                      encoding='utf-8') as f:
                yf_fundamentals = json.load(f)
            sector = yf_fundamentals.get('sectorDisp', 'Non-Financials')
            industry = yf_fundamentals.get('industryDisp', 'General')
        except FileNotFoundError:
            st.warning("yfinance 펀더멘탈 파일이 없어 업종 정보를 로드할 수 없습니다. 'Non-Financials'로 기본 설정합니다.")
            sector = 'Non-Financials'
            industry = 'General'

        st.info(f"**업종/섹터**: {sector} ({industry})")

        # 업종별 매핑
        financials_mapping = {
            "Non-Financials": {
                "income_statement": {
                    "매출액 (Revenue)": {"eodhd": "totalRevenue", "yf": "totalRevenue"},
                    "매출원가 (COGS)": {"eodhd": "costOfRevenue", "yf": "costOfRevenue"},
                    "매출이익 (Gross Profit)": {"eodhd": "grossProfit", "yf": "grossProfits"},
                    "판매관리비 (SG&A)": {"eodhd": "sellingGeneralAdministrative", "yf": "sellingGeneralAdministrative"},
                    "영업이익 (Operating Income)": {"eodhd": "operatingIncome", "yf": "operatingIncome"},
                    "세전이익 (EBT)": {"eodhd": "incomeBeforeTax", "yf": "pretaxIncome"},
                    "당기순이익 (Net Income)": {"eodhd": "netIncome", "yf": "netIncome"},
                }
            },
            "Financial Services": {
                "income_statement": {
                    "이자수익 (Interest Income)": {"eodhd": "interestIncome", "yf": "interestIncome"},
                    "이자비용 (Interest Expense)": {"eodhd": "interestExpense", "yf": "interestExpense"},
                    "순이자이익 (Net Interest Income)": {"eodhd": "netInterestIncome", "yf": "netInterestIncome"},
                    "수수료수익 (Fee & Comm.)": {"eodhd": "otherIncome", "yf": "totalRevenue"},
                    "영업이익 (Operating Profit)": {"eodhd": "operatingIncome", "yf": "operatingIncome"},
                    "세전이익 (Profit Before Tax)": {"eodhd": "incomeBeforeTax", "yf": "pretaxIncome"},
                    "당기순이익 (Net Income)": {"eodhd": "netIncome", "yf": "netIncome"},
                }
            },
            "Insurance": {
                "income_statement": {
                    "보험료수익 (Premiums Earned)": {"eodhd": "premiumIncome", "yf": "totalRevenue"},
                    "순보험손익 (Net Underwriting)": {"eodhd": "grossProfit", "yf": "grossProfits"},
                    "투자이익 (Investment Income)": {"eodhd": "investmentsGainLoss", "yf": "investmentIncome"},
                    "영업이익 (Operating Income)": {"eodhd": "operatingIncome", "yf": "operatingIncome"},
                    "당기순이익 (Net Income)": {"eodhd": "netIncome", "yf": "netIncome"},
                }
            }
        }

        def compare_financials(eodhd_values, yf_values, mapping, data_type):
            """
            EODHD와 yfinance 데이터를 매핑 기준으로 비교하여 테이블 데이터를 반환
            """
            table_data = []

            # 새 형식 매핑 사용
            sample_key = next(iter(mapping.values()))
            is_new_format = isinstance(sample_key, dict) and 'section' in sample_key

            if is_new_format:
                current_section = {
                    'income_statement': 'Income_Statement',
                    'balance_sheet': 'Balance_Sheet',
                    'cash_flow': 'Cash_Flow'
                }.get(data_type)

                # 현재 data_type에 해당하는 항목만 필터링
                filtered_mapping = {k: v for k, v in mapping.items() if v['section'] == current_section}

                for eodhd_field, field_info in filtered_mapping.items():
                    display_name = field_info['display']
                    yf_key = field_info['yf_key']

                    # EODHD 값
                    eodhd_val = eodhd_values.get(eodhd_field, 'N/A')

                    # yfinance 값
                    yf_val = yf_values.get(yf_key, 'N/A')

                    # 부분 매칭 보완
                    if yf_val == 'N/A':
                        yf_key_lower = yf_key.lower()
                        for row_name, value in yf_values.items():
                            row_name_lower = str(row_name).lower()
                            if (yf_key_lower in row_name_lower or row_name_lower in yf_key_lower):
                                yf_val = value
                                break

                    # 숫자 변환
                    def to_num(val):
                        if isinstance(val, str) and val != 'N/A':
                            try:
                                return float(val.replace(',', ''))
                            except (ValueError, AttributeError):
                                return None
                        elif isinstance(val, (int, float)):
                            return float(val)
                        return None

                    eodhd_val_num = to_num(eodhd_val)
                    yf_val_num = to_num(yf_val)

                    # 일치 여부
                    match = "❌"
                    if eodhd_val_num is not None and yf_val_num is not None:
                        if abs(eodhd_val_num - yf_val_num) / max(abs(eodhd_val_num), abs(yf_val_num), 1e-9) < 0.01:
                            match = "✅"
                        else:
                            match = "⚠️"

                    table_data.append({
                        "항목": display_name,
                        "EODHD": f"{eodhd_val_num:,.0f}" if eodhd_val_num is not None else "N/A",
                        "yfinance": f"{yf_val_num:,.0f}" if yf_val_num is not None else "N/A",
                        "일치": match
                    })

            return table_data

        def display_financial_table(title, data_type, mapping):
            st.markdown(f"**{title}**")

            # EODHD 데이터 로드
            eodhd_data = comparator.load_data(selected_ticker, data_type, source='eodhd').get('eodhd')

            # yfinance 데이터 로드 (CSV)
            yf_data = comparator.load_data(selected_ticker, data_type, source='yfinance').get('yfinance')

            # EODHD 값 추출
            eodhd_values = {}
            if eodhd_data:
                section_mapping = {
                    'income_statement': 'Income_Statement',
                    'balance_sheet': 'Balance_Sheet',
                    'cash_flow': 'Cash_Flow'
                }
                section = section_mapping.get(data_type)
                if section:
                    quarterly_data = eodhd_data.get('quarterly', {})
                    if quarterly_data:
                        latest_financial_date = max(quarterly_data.keys())
                        print('quarterly_data.keys() :::', quarterly_data.keys())
                        print('latest_financial_date :::' , latest_financial_date)
                        eodhd_values = quarterly_data[latest_financial_date]

            # yfinance 값 추출
            yf_values = {}
            if yf_data is not None and len(yf_data.columns) > 1:
                latest_column = yf_data.columns[1]
                yf_values = yf_data.set_index('index')[latest_column].to_dict()

            # 비교 수행
            table_data = compare_financials(eodhd_values, yf_values, mapping, data_type)

            # 출력
            st.table(pd.DataFrame(table_data).set_index("항목"))

        display_financial_table("손익계산서 (Income Statement)", "income_statement", all_fields_mapping)
        display_financial_table("재무상태표 (Balance Sheet)", "balance_sheet", all_fields_mapping)
        display_financial_table("현금흐름표 (Cash Flow Statement)", "cash_flow", all_fields_mapping)

        # # 손익계산서 테이블 표시
        # if "income_statement" in current_mapping:
        #     display_financial_table("손익계산서 (Income Statement)", "income_statement", current_mapping["income_statement"])
        #     st.markdown("---")
        #
        # # 재무상태표 테이블 표시
        # display_financial_table("재무상태표 (Balance Sheet)", "balance_sheet", balance_sheet_mapping)
        # st.markdown("---")
        #
        # # 현금흐름표 테이블 표시
        # display_financial_table("현금흐름표 (Cash Flow Statement)", "cash_flow", cash_flow_mapping)

    else:  # 재무제표가 아닌 경우 (historical_ohlc, dividends, fundamentals)
        # 데이터 비교 실행
        with st.spinner("데이터 품질 검증 중..."):
            comparison_results, error = comparator.compare_detailed_data(
                selected_ticker, data_type, num_records
            )

        if error:
            st.error(f"검증 실패: {error}")
            return

        if not comparison_results:
            st.warning("비교할 데이터가 없습니다. 파일이 존재하더라도 내부 데이터 구조가 예상과 다르거나, 비교할 항목이 없을 수 있습니다.")
            return

        # 결과 표시
        show_quality_report(comparison_results, comparator, selected_ticker)


def show_quality_report(comparison_results, comparator, ticker):
    """품질 보고서 표시"""

    # 요약 통계
    total_items = len(comparison_results)
    matches = len([r for r in comparison_results if r['match'] == '✅'])
    warnings = len([r for r in comparison_results if r['match'] == '⚠️'])
    errors = len([r for r in comparison_results if r['match'] == '❌'])

    st.subheader("📊 검증 결과 요약")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("총 검증 항목", total_items)
    with col2:
        st.metric("완전 일치", matches, delta=f"{matches / total_items * 100:.1f}%")
    with col3:
        st.metric("경미한 차이", warnings, delta=f"{warnings / total_items * 100:.1f}%")
    with col4:
        st.metric("중대한 차이", errors, delta=f"{errors / total_items * 100:.1f}%")

    # 상세 비교 테이블
    st.subheader("🔍 상세 검증 결과")

    # 테이블 데이터 준비
    table_data = []

    for i, result in enumerate(comparison_results):
        # 차이 원인 입력 필드
        cause_key = f"cause_{i}"
        existing_cause = result.get('existing_cause', '')

        table_data.append({
            "날짜": result['date'],
            "항목": result['field'],
            "EODHD 값": result['eodhd_value'],
            "yfinance 값": result['yfinance_value'],
            "일치 여부": result['match'],
            "차이": result['difference'] if result['difference'] != 0 else '-',
            "차이 원인": existing_cause
        })

    # 편집 가능한 테이블로 표시
    df_display = pd.DataFrame(table_data)

    # 스타일링 함수
    def highlight_matches(val):
        if val == '✅':
            return 'color: #28a745; font-weight: bold;'
        elif val == '⚠️':
            return 'color: #ffc107; font-weight: bold;'
        elif val == '❌':
            return 'color: #dc3545; font-weight: bold;'
        return ''

    styled_df = df_display.style.applymap(highlight_matches, subset=['일치 여부'])
    st.dataframe(styled_df, use_container_width=True, height=400)

    # 이슈 입력 섹션
    st.subheader("📝 이슈 원인 분석 및 기록")

    with st.expander("차이 원인 입력 및 수정", expanded=False):
        st.info("💡 발견된 차이에 대한 원인을 분석하여 입력하세요. 이 정보는 품질 보고서에 포함됩니다.")

        # 불일치 항목만 필터링
        mismatch_results = [r for r in comparison_results if r['match'] in ['❌', '⚠️']]

        if mismatch_results:
            for i, result in enumerate(mismatch_results):
                st.write(f"**{result['date']} - {result['field']}**")

                col1, col2 = st.columns([3, 1])

                with col1:
                    cause_options = comparator.common_causes
                    existing_cause = result.get('existing_cause', '')

                    if existing_cause and existing_cause not in cause_options:
                        cause_options = [existing_cause] + cause_options

                    selected_cause = st.selectbox(
                        "차이 원인:",
                        options=cause_options,
                        index=cause_options.index(existing_cause) if existing_cause in cause_options else len(
                            cause_options) - 1,
                        key=f"cause_select_{i}"
                    )

                    if selected_cause == "기타":
                        custom_cause = st.text_input(
                            "기타 원인 상세 입력:",
                            value=existing_cause if existing_cause not in comparator.common_causes[:-1] else '',
                            key=f"custom_cause_{i}"
                        )
                        final_cause = custom_cause if custom_cause else selected_cause
                    else:
                        final_cause = selected_cause

                with col2:
                    if st.button("💾 저장", key=f"save_{i}"):
                        issue_data = {
                            'field': result['field'],
                            'date': result['date'],
                            'eodhd_value': result['eodhd_value'],
                            'yfinance_value': result['yfinance_value'],
                            'difference': result['difference'],
                            'cause': final_cause,
                            'status': 'documented'
                        }

                        comparator.issue_tracker.add_issue(ticker, result['field'], issue_data)
                        st.success("✅ 이슈가 저장되었습니다!")
                        st.rerun()

                st.divider()
        else:
            st.success("🎉 모든 데이터가 일치합니다! 이슈가 발견되지 않았습니다.")


def generate_final_report(results, ticker, client_name, report_date, analyst_name, report_type, comparator):
    """최종 보고서 생성"""

    # 통계 계산
    total_items = len(results)
    matches = len([r for r in results if r['match'] == '✅'])
    warnings = len([r for r in results if r['match'] == '⚠️'])
    errors = len([r for r in results if r['match'] == '❌'])

    accuracy_rate = (matches / total_items * 100) if total_items > 0 else 0

    # 보고서 HTML 생성
    report_html = f"""
    <div style="max-width: 800px; margin: 0 auto; font-family: Arial, sans-serif;">
        <div style="text-align: center; border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 30px;">
            <h1 style="color: #333;">데이터 품질 검증 보고서</h1>
            <h2 style="color: #666;">{ticker} 종목</h2>
            <p><strong>고객:</strong> {client_name} | <strong>작성일:</strong> {report_date} | <strong>분석가:</strong> {analyst_name}</p>
            <p><strong>보고서 유형:</strong> {report_type}</p>
        </div>

        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 30px;">
            <h3>📊 검증 결과 요약</h3>
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; text-align: center;">
                <div>
                    <h4 style="color: #007bff;">총 검증 항목</h4>
                    <p style="font-size: 24px; font-weight: bold;">{total_items}</p>
                </div>
                <div>
                    <h4 style="color: #28a745;">완전 일치</h4>
                    <p style="font-size: 24px; font-weight: bold;">{matches}</p>
                </div>
                <div>
                    <h4 style="color: #ffc107;">경미한 차이</h4>
                    <p style="font-size: 24px; font-weight: bold;">{warnings}</p>
                </div>
                <div>
                    <h4 style="color: #dc3545;">중대한 차이</h4>
                    <p style="font-size: 24px; font-weight: bold;">{errors}</p>
                </div>
            </div>
            <div style="text-align: center; margin-top: 20px;">
                <h3 style="color: #333;">데이터 정확도: {accuracy_rate:.1f}%</h3>
            </div>
        </div>

        <div style="margin-bottom: 30px;">
            <h3>🔍 상세 검증 결과</h3>
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                <thead>
                    <tr style="background-color: #e9ecef;">
                        <th style="border: 1px solid #dee2e6; padding: 12px; text-align: left;">날짜</th>
                        <th style="border: 1px solid #dee2e6; padding: 12px; text-align: left;">항목</th>
                        <th style="border: 1px solid #dee2e6; padding: 12px; text-align: right;">EODHD 값</th>
                        <th style="border: 1px solid #dee2e6; padding: 12px; text-align: right;">yfinance 값</th>
                        <th style="border: 1px solid #dee2e6; padding: 12px; text-align: center;">일치 여부</th>
                        <th style="border: 1px solid #dee2e6; padding: 12px; text-align: left;">차이 원인</th>
                    </tr>
                </thead>
                <tbody>
    """

    for result in results:
        existing_issues = comparator.issue_tracker.get_issues(ticker)
        issue_key = f"{result['field']}_{result['date']}"
        cause = existing_issues.get(issue_key, {}).get('cause', '-')

        match_color = '#28a745' if result['match'] == '✅' else '#ffc107' if result['match'] == '⚠️' else '#dc3545'

        report_html += f"""
                    <tr>
                        <td style="border: 1px solid #dee2e6; padding: 8px;">{result['date']}</td>
                        <td style="border: 1px solid #dee2e6; padding: 8px;">{result['field']}</td>
                        <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">{result['eodhd_value']}</td>
                        <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">{result['yfinance_value']}</td>
                        <td style="border: 1px solid #dee2e6; padding: 8px; text-align: center; color: {match_color}; font-weight: bold;">{result['match']}</td>
                        <td style="border: 1px solid #dee2e6; padding: 8px;">{cause}</td>
                    </tr>
        """

    report_html += f"""
                </tbody>
            </table>
        </div>

        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px;">
            <h3>📋 분석 결론</h3>
            <p><strong>{ticker}</strong> 종목의 데이터 품질 검증 결과, 전체 {total_items}개 항목 중 {matches}개 항목이 완전히 일치하여 
            <strong>{accuracy_rate:.1f}%</strong>의 정확도를 보였습니다.</p>

            {'<p style="color: #28a745;"><strong>✅ 모든 데이터가 정상적으로 일치합니다.</strong></p>' if errors == 0 and warnings == 0 else ''}

            {'<p style="color: #ffc107;"><strong>⚠️ 경미한 차이가 발견되었으나 허용 범위 내입니다.</strong></p>' if warnings > 0 and errors == 0 else ''}

            {'<p style="color: #dc3545;"><strong>❌ 중대한 차이가 발견되었습니다. 추가 검토가 필요합니다.</strong></p>' if errors > 0 else ''}

            <p>본 보고서는 데이터 제공업체 간 품질 차이를 분석하여 투자 결정에 필요한 신뢰성 있는 정보를 제공하기 위해 작성되었습니다.</p>
        </div>

        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6; text-align: center; color: #6c757d;">
            <p>본 보고서는 {analyst_name}에 의해 {report_date}에 작성되었습니다.</p>
            <p>© 2024 Data Quality Assurance Team. All rights reserved.</p>
        </div>
    </div>
    """

    # HTML을 컨테이너에 표시
    st.markdown("### 📄 최종 보고서")
    st.markdown(report_html, unsafe_allow_html=True)

    # 보고서 다운로드 기능
    st.markdown("---")
    st.subheader("💾 보고서 다운로드")

    col1, col2 = st.columns(2)

    with col1:
        # HTML 다운로드
        html_bytes = report_html.encode('utf-8')
        st.download_button(
            label="📄 HTML 보고서 다운로드",
            data=html_bytes,
            file_name=f"data_quality_report_{ticker}_{report_date.strftime('%Y%m%d')}.html",
            mime="text/html"
        )

    with col2:
        # CSV 다운로드
        csv_data = []
        for result in results:
            existing_issues = comparator.issue_tracker.get_issues(ticker)
            issue_key = f"{result['field']}_{result['date']}"
            cause = existing_issues.get(issue_key, {}).get('cause', '')

            csv_data.append({
                '날짜': result['date'],
                '항목': result['field'],
                'EODHD_값': result['eodhd_value'],
                'yfinance_값': result['yfinance_value'],
                '일치_여부': result['match'],
                '차이': result['difference'] if result['difference'] != 0 else '',
                '차이_원인': cause
            })

        csv_df = pd.DataFrame(csv_data)
        csv_string = csv_df.to_csv(index=False, encoding='utf-8-sig')

        st.download_button(
            label="📊 CSV 데이터 다운로드",
            data=csv_string,
            file_name=f"data_quality_data_{ticker}_{report_date.strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

    # 이슈 히스토리 표시
    st.markdown("---")
    st.subheader("📚 이슈 히스토리")

    all_issues = comparator.issue_tracker.get_issues(ticker)
    if all_issues:
        issue_history = []
        for issue_key, issue_data in all_issues.items():
            issue_history.append({
                '필드': issue_data.get('field', ''),
                '날짜': issue_data.get('date', ''),
                '원인': issue_data.get('cause', ''),
                '상태': issue_data.get('status', ''),
                '업데이트': issue_data.get('updated_at', '').split('T')[0] if issue_data.get('updated_at') else ''
            })

        if issue_history:
            issue_df = pd.DataFrame(issue_history)
            st.dataframe(issue_df, use_container_width=True)
        else:
            st.info("아직 기록된 이슈가 없습니다.")
    else:
        st.info("아직 기록된 이슈가 없습니다.")


def show_issue_management():
    """이슈 관리 페이지"""
    st.subheader("🛠️ 이슈 관리")

    comparator = DataComparator()
    all_issues = comparator.issue_tracker.get_issues()

    if not all_issues:
        st.info("현재 등록된 이슈가 없습니다.")
        return

    # 이슈 통계
    total_issues = sum(len(ticker_issues) for ticker_issues in all_issues.values())
    open_issues = sum(1 for ticker_issues in all_issues.values()
                      for issue in ticker_issues.values()
                      if issue.get('status') == 'open')
    documented_issues = total_issues - open_issues

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("전체 이슈", total_issues)
    with col2:
        st.metric("미해결", open_issues)
    with col3:
        st.metric("문서화 완료", documented_issues)

    # 이슈 목록 표시
    st.subheader("📋 전체 이슈 목록")

    issue_list = []
    for ticker, ticker_issues in all_issues.items():
        for issue_key, issue_data in ticker_issues.items():
            issue_list.append({
                '종목': ticker,
                '필드': issue_data.get('field', ''),
                '날짜': issue_data.get('date', ''),
                'EODHD': issue_data.get('eodhd_value', ''),
                'yfinance': issue_data.get('yfinance_value', ''),
                '차이': issue_data.get('difference', ''),
                '원인': issue_data.get('cause', ''),
                '상태': issue_data.get('status', ''),
                '업데이트': issue_data.get('updated_at', '').split('T')[0] if issue_data.get('updated_at') else ''
            })

    if issue_list:
        issue_df = pd.DataFrame(issue_list)

        # 필터링 옵션
        col1, col2 = st.columns(2)
        with col1:
            status_filter = st.selectbox("상태 필터:", ["전체", "open", "documented"])
        with col2:
            ticker_filter = st.selectbox("종목 필터:", ["전체"] + list(all_issues.keys()))

        # 필터 적용
        filtered_df = issue_df.copy()
        if status_filter != "전체":
            filtered_df = filtered_df[filtered_df['상태'] == status_filter]
        if ticker_filter != "전체":
            filtered_df = filtered_df[filtered_df['종목'] == ticker_filter]

        st.dataframe(filtered_df, use_container_width=True)

        # 이슈 삭제 기능
        st.subheader("🗑️ 이슈 관리")
        if st.button("⚠️ 모든 이슈 초기화", type="secondary"):
            if st.checkbox("정말로 모든 이슈를 삭제하시겠습니까?"):
                comparator.issue_tracker.issues = {}
                comparator.issue_tracker.save_issues()
                st.success("모든 이슈가 삭제되었습니다.")
                st.rerun()


# 메인 실행
if __name__ == "__main__":
    # 페이지 네비게이션
    page = st.sidebar.selectbox("페이지 선택", ["품질 검증", "이슈 관리"])

    if page == "품질 검증":
        main()
    else:
        show_issue_management()
    # comparator = DataComparator()
    # ticker_list = comparator.get_ticker_list()
    # print(1)
    # df = pd.DataFrame(data=ticker_list)
    #
    # df.to_parquet(path='./tickers', engine="pyarrow", compression="gzip")