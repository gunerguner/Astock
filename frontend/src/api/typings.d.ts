declare namespace API {
  type ApiResponse<T = unknown> = {
    code: number;
    message: string;
    data: T;
  };

  // ---- analysis: bull market ----

  type BullMarketItem = {
    market: string;
    start: string;
    end: string;
    description: string;
    days: number;
    max_value: number | null;
    not_available?: boolean;
  };

  type BullMarketStats = {
    threshold: number;
    items: BullMarketItem[];
    total_days: number;
  };

  type IndexPointStats = {
    index_code: string;
    index_name: string;
    threshold: number;
    items: BullMarketItem[];
    total_days: number;
  };

  type MultiIndexPointStats = {
    indices: IndexPointStats[];
  };

  type PointIndexCode = '000001' | '000300' | '399006' | '000688';

  type PointThresholds = Record<PointIndexCode, number>;

  // ---- analysis: rankings ----

  type TurnoverRankingItem = {
    rank: number;
    date: string;
    sse_amount: number;
    szse_amount: number;
    turnover: number;
  };

  type TurnoverRanking = {
    top: number;
    bull_market: string | null;
    items: TurnoverRankingItem[];
  };

  type StockRankingItem = {
    rank: number;
    date: string;
    code: string;
    name: string;
    amount: number;
  };

  type StockRanking = {
    top: number;
    bull_market: string | null;
    items: StockRankingItem[];
  };

  // ---- analysis: asset price levels ----

  type PriceLevelConclusion =
    | 'pending'
    | 'nearAth'
    | 'moderatePullback'
    | 'significantPullback'
    | 'deepPullback';

  type PriceLevelPendingItem = {
    ticker: string;
    name: string;
    asset_type: 'stock' | 'metal';
    conclusion: PriceLevelConclusion;
    data_pending: true;
  };

  type PriceLevelDataItem = {
    ticker: string;
    name: string;
    asset_type: 'stock' | 'metal';
    current_price: number;
    all_time_high: number;
    ath_date: string;
    percentage_diff: number;
    ath_days: number;
    daily_change: number | null;
    weekly_change: number | null;
    conclusion: PriceLevelConclusion;
  };

  type PriceLevelRow = PriceLevelDataItem | PriceLevelPendingItem;

  type AssetPriceLevels = {
    last_synced_at: string | null;
    as_of: string;
    latest_trading_date: string;
    items: PriceLevelRow[];
    cache_errors: string[];
  };

  // ---- analysis: market overview ----

  type MarketOverviewErrorItem = {
    key: string;
    name: string;
    code: string;
    error: string;
  };

  type MarketOverviewDataItem = {
    key: string;
    name: string;
    code: string;
    current_price: number;
    daily_change: number | null;
    weekly_change: number | null;
    period_start: string;
    period_end: string;
  };

  type MarketOverviewRow = MarketOverviewDataItem | MarketOverviewErrorItem;

  type MarketOverviewCategory = {
    key: string;
    name: string;
    items: MarketOverviewRow[];
  };

  type MarketOverview = {
    as_of: string;
    latest_trading_date: string;
    categories: MarketOverviewCategory[];
    errors: string[];
  };

  // ---- analysis: macro ----

  type UsMacroPointItem = {
    period: string;
    cpi_yoy: number | null;
    fed_rate_upper: number | null;
  };

  type UsMacroData = {
    start: string;
    latest_period: string | null;
    last_synced_at: string | null;
    points: UsMacroPointItem[];
  };

  type CnMacroPointItem = {
    period: string;
    cpi_yoy: number | null;
    ppi_yoy: number | null;
    pmi_manufacturing: number | null;
    pmi_non_manufacturing: number | null;
    consumer_confidence: number | null;
  };

  type CnMacroData = {
    start: string;
    latest_period: string | null;
    last_synced_at: string | null;
    points: CnMacroPointItem[];
  };

  // ---- admin: import / sync ----

  type ImportStatus = 'failed' | 'partial_failure' | 'success';

  type ImportResultItem = {
    imported: number;
    total: number;
    last_date: string | null;
    last_synced_at: string | null;
    status: ImportStatus;
    source_errors: Record<string, string>;
    elapsed: number;
  };

  type ImportAllResult = {
    turnover: ImportResultItem;
    point: ImportResultItem;
    stock: ImportResultItem;
    global_assets?: ImportResultItem;
    us_macro?: ImportResultItem;
    cn_macro?: ImportResultItem;
    status: ImportStatus;
  };

  type ImportPhaseKey =
    'turnover' | 'point' | 'stock' | 'global_assets' | 'us_macro' | 'cn_macro';

  type ImportProgressEvent = {
    phase: ImportPhaseKey;
    label: string;
    status: 'running' | 'done' | 'failed';
    current: number;
    total: number;
    imported: number;
    detail?: string;
    elapsed?: number;
    source_errors?: Record<string, string>;
  };

  type ImportStreamError = {
    message: string;
    phase?: ImportPhaseKey;
  };

  type ImportStreamHandlers = {
    onProgress?: (event: ImportProgressEvent) => void;
    onDone?: (result: ImportAllResult) => void;
    onError?: (error: ImportStreamError | { message: string }) => void;
  };

  type SyncStatusItem = {
    last_synced_date: string | null;
    last_synced_at: string | null;
    status: ImportStatus | null;
  };

  type SyncStatus = {
    turnover: SyncStatusItem;
    point: SyncStatusItem;
    stock: SyncStatusItem;
    global_assets: SyncStatusItem;
    us_macro: SyncStatusItem;
    cn_macro: SyncStatusItem;
  };
}
