import type { DefaultTheme } from "vitepress";

const dauTuDay = (
  text: string,
  part: string,
  slug: string,
): DefaultTheme.SidebarItem => ({
  text,
  link: `/dau-tu/${part}/${slug}/lesson`,
});

export const dauTuSidebar: DefaultTheme.SidebarItem[] = [
  {
    text: "Đầu tư A-Z",
    items: [
      { text: "Overview", link: "/dau-tu/" },
      { text: "Review tổng thể", link: "/dau-tu/review-task" },
    ],
  },
  {
    text: "Phần 1 - Kinh tế nền tảng",
    items: [
      dauTuDay(
        "Day 01 - Tại sao phải đầu tư",
        "phan-1-kinh-te-vi-mo-va-vi-mo",
        "day-01-tai-sao-phai-dau-tu",
      ),
      dauTuDay(
        "Day 02 - Các loại tài sản đầu tư",
        "phan-1-kinh-te-vi-mo-va-vi-mo",
        "day-02-cac-loai-tai-san-dau-tu",
      ),
      dauTuDay(
        "Day 03 - Supply and Demand",
        "phan-1-kinh-te-vi-mo-va-vi-mo",
        "day-03-supply-and-demand",
      ),
      dauTuDay(
        "Day 04 - Cấu trúc thị trường & Moat",
        "phan-1-kinh-te-vi-mo-va-vi-mo",
        "day-04-cau-truc-thi-truong-economic-moat",
      ),
      dauTuDay(
        "Day 05 - Hành vi doanh nghiệp",
        "phan-1-kinh-te-vi-mo-va-vi-mo",
        "day-05-hanh-vi-doanh-nghiep",
      ),
      dauTuDay(
        "Day 06 - Hành vi người tiêu dùng",
        "phan-1-kinh-te-vi-mo-va-vi-mo",
        "day-06-hanh-vi-nguoi-tieu-dung-nha-dau-tu",
      ),
      dauTuDay(
        "Day 07 - Market Failure",
        "phan-1-kinh-te-vi-mo-va-vi-mo",
        "day-07-on-tap-tuan-1-market-failure",
      ),
      dauTuDay(
        "Day 08 - GDP & Business Cycle",
        "phan-1-kinh-te-vi-mo-va-vi-mo",
        "day-08-gdp-business-cycle",
      ),
      dauTuDay(
        "Day 09 - Inflation & Deflation",
        "phan-1-kinh-te-vi-mo-va-vi-mo",
        "day-09-inflation-deflation",
      ),
      dauTuDay(
        "Day 10 - Interest Rate",
        "phan-1-kinh-te-vi-mo-va-vi-mo",
        "day-10-interest-rate",
      ),
      dauTuDay(
        "Day 11 - Monetary Policy",
        "phan-1-kinh-te-vi-mo-va-vi-mo",
        "day-11-monetary-policy",
      ),
      dauTuDay(
        "Day 12 - Fiscal Policy",
        "phan-1-kinh-te-vi-mo-va-vi-mo",
        "day-12-fiscal-policy",
      ),
      dauTuDay(
        "Day 13 - Exchange Rate & Trade",
        "phan-1-kinh-te-vi-mo-va-vi-mo",
        "day-13-exchange-rate-international-trade",
      ),
      dauTuDay(
        "Day 14 - Employment & Phillips Curve",
        "phan-1-kinh-te-vi-mo-va-vi-mo",
        "day-14-employment-phillips-curve",
      ),
      dauTuDay(
        "Day 15 - Hệ thống tài chính",
        "phan-1-kinh-te-vi-mo-va-vi-mo",
        "day-15-he-thong-tai-chinh",
      ),
      dauTuDay(
        "Day 16 - Economic Calendar",
        "phan-1-kinh-te-vi-mo-va-vi-mo",
        "day-16-economic-calendar",
      ),
      dauTuDay(
        "Day 17 - Geopolitics",
        "phan-1-kinh-te-vi-mo-va-vi-mo",
        "day-17-geopolitics",
      ),
      dauTuDay(
        "Day 18 - Khủng hoảng tài chính",
        "phan-1-kinh-te-vi-mo-va-vi-mo",
        "day-18-khung-hoang-tai-chinh-tong-on-tap",
      ),
    ],
  },
  {
    text: "Phần 2 - Fundamental Analysis",
    items: [
      dauTuDay("Day 19 - Risk Management", "phan-2-fundamental-analysis", "day-19-risk-management"),
      dauTuDay("Day 20 - Income Statement", "phan-2-fundamental-analysis", "day-20-income-statement"),
      dauTuDay("Day 21 - Balance Sheet & Cash Flow", "phan-2-fundamental-analysis", "day-21-balance-sheet-cash-flow"),
      dauTuDay("Day 22 - Valuation Ratios", "phan-2-fundamental-analysis", "day-22-valuation-ratios"),
      dauTuDay("Day 23 - Valuation Methods & DCF", "phan-2-fundamental-analysis", "day-23-valuation-methods-dcf"),
      dauTuDay("Day 24 - Industry Analysis", "phan-2-fundamental-analysis", "day-24-industry-analysis"),
      dauTuDay("Day 25 - Thực hành phân tích cơ bản", "phan-2-fundamental-analysis", "day-25-thuc-hanh-phan-tich-co-ban"),
    ],
  },
  {
    text: "Phần 3 - Technical Analysis",
    items: [
      dauTuDay("Day 26 - Candlestick cơ bản", "phan-3-technical-analysis", "day-26-candlestick-co-ban"),
      dauTuDay("Day 27 - Candlestick nâng cao", "phan-3-technical-analysis", "day-27-candlestick-nang-cao"),
      dauTuDay("Day 28 - Trend, Support & Resistance", "phan-3-technical-analysis", "day-28-trend-support-resistance"),
      dauTuDay("Day 29 - Chart Patterns", "phan-3-technical-analysis", "day-29-chart-patterns"),
      dauTuDay("Day 30 - Indicators Trend Following", "phan-3-technical-analysis", "day-30-indicators-trend-following"),
      dauTuDay("Day 31 - Oscillators & Volume", "phan-3-technical-analysis", "day-31-indicators-oscillators-volume"),
      dauTuDay("Day 32 - Price Action Trading Plan", "phan-3-technical-analysis", "day-32-price-action-trading-plan"),
    ],
  },
  {
    text: "Phần 4 - Stock Market",
    items: [
      dauTuDay("Day 33 - Chứng khoán cơ bản", "phan-4-stock-market", "day-33-chung-khoan-co-ban"),
      dauTuDay("Day 34 - Margin & Short Selling", "phan-4-stock-market", "day-34-margin-short-selling"),
      dauTuDay("Day 35 - Value Investing", "phan-4-stock-market", "day-35-value-investing"),
      dauTuDay("Day 36 - Growth Investing", "phan-4-stock-market", "day-36-growth-investing"),
      dauTuDay("Day 37 - DCA & Dividend Investing", "phan-4-stock-market", "day-37-dca-dividend-investing"),
      dauTuDay("Day 38 - ETF & Index Fund", "phan-4-stock-market", "day-38-etf-index-fund"),
      dauTuDay("Day 39 - Market Indices", "phan-4-stock-market", "day-39-market-indices"),
      dauTuDay("Day 40 - IPO, M&A & Corporate Actions", "phan-4-stock-market", "day-40-ipo-ma-corporate-actions"),
      dauTuDay("Day 41 - Portfolio Management", "phan-4-stock-market", "day-41-portfolio-management"),
      dauTuDay("Day 42 - Thực hành tổng hợp Stock", "phan-4-stock-market", "day-42-thuc-hanh-tong-hop-stock"),
    ],
  },
  {
    text: "Phần 5 - Forex",
    items: [
      dauTuDay("Day 43 - Forex cơ bản", "phan-5-forex", "day-43-forex-co-ban"),
      dauTuDay("Day 44 - Pip, Lot, Leverage, Spread", "phan-5-forex", "day-44-pip-lot-leverage-spread"),
      dauTuDay("Day 45 - Fundamental Analysis Forex", "phan-5-forex", "day-45-fundamental-analysis-forex"),
      dauTuDay("Day 46 - Carry Trade & Central Bank", "phan-5-forex", "day-46-carry-trade-central-bank"),
      dauTuDay("Day 47 - Technical Analysis Forex", "phan-5-forex", "day-47-technical-analysis-forex"),
      dauTuDay("Day 48 - Forex Trading Strategies", "phan-5-forex", "day-48-forex-trading-strategies"),
      dauTuDay("Day 49 - Money Management Forex", "phan-5-forex", "day-49-money-management-forex"),
      dauTuDay("Day 50 - Trading Psychology", "phan-5-forex", "day-50-trading-psychology"),
      dauTuDay("Day 51 - Chọn Broker & Platform", "phan-5-forex", "day-51-chon-broker-platform"),
      dauTuDay("Day 52 - Thực hành tổng hợp Forex", "phan-5-forex", "day-52-thuc-hanh-tong-hop-forex"),
    ],
  },
  {
    text: "Phần 6 - Crypto",
    items: [
      dauTuDay("Day 53 - Blockchain & Bitcoin cơ bản", "phan-6-crypto", "day-53-blockchain-bitcoin-co-ban"),
      dauTuDay("Day 54 - Ethereum & Smart Contracts", "phan-6-crypto", "day-54-ethereum-smart-contracts"),
      dauTuDay("Day 55 - Crypto Ecosystem, DeFi & NFT", "phan-6-crypto", "day-55-crypto-ecosystem-defi-nft"),
      dauTuDay("Day 56 - Tokenomics", "phan-6-crypto", "day-56-tokenomics"),
      dauTuDay("Day 57 - Wallet Security", "phan-6-crypto", "day-57-wallet-security"),
      dauTuDay("Day 58 - Crypto Fundamental Analysis", "phan-6-crypto", "day-58-crypto-fundamental-analysis"),
      dauTuDay("Day 59 - Scam & Risk Management", "phan-6-crypto", "day-59-scam-risk-management"),
      dauTuDay("Day 60 - Crypto Trading Strategies", "phan-6-crypto", "day-60-crypto-trading-strategies"),
      dauTuDay("Day 61 - Bitcoin Halving & Market Cycle", "phan-6-crypto", "day-61-bitcoin-halving-market-cycle"),
      dauTuDay("Day 62 - Tổng kết khóa học", "phan-6-crypto", "day-62-tong-ket-khoa-hoc"),
    ],
  },
  {
    text: "Phần bổ sung",
    items: [
      dauTuDay(
        "Day 63 - Công cụ nền tảng giao dịch",
        "phan-bo-sung",
        "day-63-cong-cu-nen-tang-giao-dich",
      ),
    ],
  },
];
