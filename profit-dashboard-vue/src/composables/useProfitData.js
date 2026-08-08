import { computed, ref } from 'vue';

const apiBase = import.meta.env.VITE_API_BASE || '';
const demoMode = import.meta.env.VITE_DEMO_MODE === 'true';
const demoBase = `${import.meta.env.BASE_URL || './'}demo-data`;
const demoPeriod = '2026-07-01_2026-07-14';
const demoCache = new Map();

const demoKeys = {
  linkId: '\u94fe\u63a5id',
  productCode: '\u5546\u54c1\u7f16\u7801',
  title: '\u5546\u54c1\u6807\u9898',
  creationTime: '\u94fe\u63a5\u521b\u5efa\u65f6\u95f4',
  storeName: '\u5e97\u94fa\u540d\u79f0',
  person: '\u8d1f\u8d23\u4eba',
  date: '\u6570\u636e\u65e5\u671f',
};

async function loadDemoJson(filename) {
  if (!demoCache.has(filename)) {
    demoCache.set(filename, fetch(`${demoBase}/${filename}`).then(async (response) => {
      if (!response.ok) throw new Error(`Demo fixture request failed (${response.status})`);
      return response.json();
    }));
  }
  return demoCache.get(filename);
}

function splitDemoFilter(value) {
  return String(value || '').split(',').map((item) => item.trim()).filter(Boolean);
}

function inDemoDateRange(value, start, end) {
  const date = String(value || '').slice(0, 10);
  return (!start || date >= start) && (!end || date <= end);
}

function demoBrandFromStore(value) {
  const store = String(value || '');
  if (store.includes('浪奇')) return '浪奇';
  if (store.includes('威王') || store.toUpperCase().includes('VEWIN')) return '威王';
  if (store.includes('舒蕾') || store.toUpperCase().includes('SLEK')) return '舒蕾';
  return '白牌';
}

function demoRowMatches(row, params = {}) {
  const linkIds = splitDemoFilter(params.link_ids);
  if (linkIds.length && !linkIds.includes(String(row[demoKeys.linkId] ?? ''))) return false;
  if (params.product_code && !String(row[demoKeys.productCode] ?? '').toLowerCase().includes(String(params.product_code).toLowerCase())) return false;
  if (params.product_name && !String(row[demoKeys.title] ?? '').toLowerCase().includes(String(params.product_name).toLowerCase())) return false;
  if (params.brand && demoBrandFromStore(row[demoKeys.storeName]) !== params.brand) return false;
  if (params.store_name && !String(row[demoKeys.storeName] ?? '').toLowerCase().includes(String(params.store_name).toLowerCase())) return false;
  if (params.store_person && String(row[demoKeys.person] ?? '') !== String(params.store_person)) return false;
  if (params.search) {
    const search = String(params.search).toLowerCase();
    const haystack = [demoKeys.linkId, demoKeys.productCode, demoKeys.title, demoKeys.storeName].map((key) => String(row[key] ?? '').toLowerCase());
    if (!haystack.some((value) => value.includes(search))) return false;
  }
  if (row[demoKeys.date] !== undefined && !inDemoDateRange(row[demoKeys.date], params.start, params.end)) return false;
  if (params.creation_start || params.creation_end) {
    const created = String(row[demoKeys.creationTime] || '').slice(0, 10).replaceAll('/', '-');
    if ((params.creation_start && created < params.creation_start) || (params.creation_end && created > params.creation_end)) return false;
  }

  if (params.filter_json) {
    let filters = [];
    try { filters = JSON.parse(params.filter_json) || []; } catch { filters = []; }
    for (const filter of filters) {
      if (filter.field === '链接id') {
        const filterLinkIds = splitDemoFilter(filter.v1);
        if (filterLinkIds.length && !filterLinkIds.includes(String(row[demoKeys.linkId] ?? ''))) return false;
        continue;
      }
      const value = filter.field === '品牌' ? demoBrandFromStore(row[demoKeys.storeName]) : row[filter.field];
      const text = String(value ?? '').toLowerCase();
      const v1 = String(filter.v1 ?? '').toLowerCase();
      const v2 = String(filter.v2 ?? '').toLowerCase();
      if (filter.op === 'equals' || filter.op === 'eq') {
        if (text !== v1) return false;
      } else if (filter.op === 'gte' || filter.op === 'lte' || filter.op === 'between') {
        const left = Number(value);
        const lower = Number(filter.v1);
        const upper = Number(filter.v2);
        if (Number.isNaN(left)) return false;
        if (filter.op === 'gte' && left < lower) return false;
        if (filter.op === 'lte' && left > lower) return false;
        if (filter.op === 'between' && ((filter.v1 && left < lower) || (filter.v2 && left > upper))) return false;
      } else if (!text.includes(v1)) {
        return false;
      }
    }
  }
  return true;
}

function demoPage(rows, page = 1, size = 20) {
  const safeSize = Math.max(1, Number(size) || 20);
  const total = rows.length;
  const pages = total ? Math.ceil(total / safeSize) : 0;
  const safePage = pages ? Math.min(Math.max(1, Number(page) || 1), pages) : 1;
  return { data: rows.slice((safePage - 1) * safeSize, safePage * safeSize), total, page: safePage, size: safeSize, pages };
}

function demoLinkSummary(rows, params = {}) {
  const groups = new Map();
  const sum = (value) => Number(value || 0);
  const ratio = (numerator, denominator) => denominator ? Number((numerator / denominator * 100).toFixed(1)) : 0;
  const brand = (store) => {
    const text = String(store || '');
    if (text.includes('浪奇')) return '浪奇';
    if (text.includes('威王') || text.toUpperCase().includes('VEWIN')) return '威王';
    if (text.includes('舒蕾') || text.toUpperCase().includes('SLEK')) return '舒蕾';
    return '白牌';
  };
  const filteredRows = rows.filter((row) => demoRowMatches(row, params));
  filteredRows.forEach((row) => {
    const linkId = String(row[demoKeys.linkId] ?? '');
    if (!linkId) return;
    const current = groups.get(linkId) || {
      linkId,
      productCode: row[demoKeys.productCode] || '',
      title: row[demoKeys.title] || '',
      storeName: row[demoKeys.storeName] || '',
      person: row[demoKeys.person] || '',
      dates: [],
      orders: 0,
      revenue: 0,
      cost: 0,
      shipping: 0,
      grossProfit: 0,
      techServiceFee: 0,
      estimatedAfterSale: 0,
      promotion: 0,
      freightInsurance: 0,
      tax: 0,
      platformProfit: 0,
    };
    current.productCode ||= row[demoKeys.productCode] || '';
    current.title ||= row[demoKeys.title] || '';
    current.storeName ||= row[demoKeys.storeName] || '';
    current.person ||= row[demoKeys.person] || '';
    current.dates.push(String(row[demoKeys.date] || '').slice(0, 10));
    current.orders += sum(row['单量']);
    current.revenue += sum(row['收入']);
    current.cost += sum(row['成本']);
    current.shipping += sum(row['快递']);
    current.grossProfit += sum(row['毛利']);
    current.techServiceFee += sum(row['技术服务费']);
    current.estimatedAfterSale += sum(row['预估售后']);
    current.promotion += sum(row['推广费']);
    current.freightInsurance += sum(row['运费险']);
    current.tax += sum(row['税费']);
    current.platformProfit += sum(row['平台利润']);
    groups.set(linkId, current);
  });
  const toSummaryRow = (group) => {
    const dates = [...new Set(group.dates.filter(Boolean))].sort();
    const costShipping = group.cost + group.shipping;
    return {
      linkId: group.linkId,
      productCode: group.productCode,
      title: group.title,
      storeName: group.storeName,
      brand: brand(group.storeName),
      person: group.person,
      firstDate: dates[0] || '',
      lastDate: dates.at(-1) || '',
      dataDays: dates.length,
      orders: Math.round(group.orders),
      revenue: Number(group.revenue.toFixed(2)),
      cost: Number(group.cost.toFixed(2)),
      costPct: ratio(group.cost, group.revenue),
      shipping: Number(group.shipping.toFixed(2)),
      shippingPct: ratio(group.shipping, group.revenue),
      costShipping: Number(costShipping.toFixed(2)),
      costShippingPct: ratio(costShipping, group.revenue),
      grossProfit: Number(group.grossProfit.toFixed(2)),
      grossMargin: ratio(group.grossProfit, group.revenue),
      techServiceFee: Number(group.techServiceFee.toFixed(2)),
      estimatedAfterSale: Number(group.estimatedAfterSale.toFixed(2)),
      promotion: Number(group.promotion.toFixed(2)),
      promotionPct: ratio(group.promotion, group.revenue),
      freightInsurance: Number(group.freightInsurance.toFixed(2)),
      tax: Number(group.tax.toFixed(2)),
      platformProfit: Number(group.platformProfit.toFixed(2)),
      profitRate: ratio(group.platformProfit, group.revenue),
    };
  };
  const allRows = [...groups.values()].map(toSummaryRow);
  const sortKeyMap = {
    linkId: 'linkId', productCode: 'productCode', title: 'title', storeName: 'storeName', brand: 'brand', person: 'person',
    firstDate: 'firstDate', lastDate: 'lastDate', dataDays: 'dataDays', orders: 'orders', revenue: 'revenue', cost: 'cost', costPct: 'costPct',
    shipping: 'shipping', shippingPct: 'shippingPct', costShipping: 'costShipping', costShippingPct: 'costShippingPct', grossProfit: 'grossProfit',
    grossMargin: 'grossMargin', promotion: 'promotion', promotionPct: 'promotionPct', platformProfit: 'platformProfit', profitRate: 'profitRate',
  };
  const sortKey = sortKeyMap[params.sort_by] || 'revenue';
  const sortDirection = params.sort_order === 'asc' ? 1 : -1;
  allRows.sort((left, right) => {
    const leftValue = left[sortKey];
    const rightValue = right[sortKey];
    if (typeof leftValue === 'number' && typeof rightValue === 'number') return (leftValue - rightValue) * sortDirection;
    return String(leftValue ?? '').localeCompare(String(rightValue ?? ''), 'zh-CN') * sortDirection;
  });
  const totals = allRows.reduce((result, row) => {
    result.orders += row.orders;
    result.revenue += row.revenue;
    result.cost += row.cost;
    result.shipping += row.shipping;
    result.grossProfit += row.grossProfit;
    result.promotion += row.promotion;
    result.platformProfit += row.platformProfit;
    return result;
  }, { orders: 0, revenue: 0, cost: 0, shipping: 0, grossProfit: 0, promotion: 0, platformProfit: 0 });
  const dates = [...new Set(filteredRows.map((row) => String(row[demoKeys.date] || '').slice(0, 10)).filter(Boolean))].sort();
  const summary = {
    links: allRows.length,
    rows: filteredRows.length,
    dataDays: dates.length,
    firstDate: dates[0] || '',
    lastDate: dates.at(-1) || '',
    ...totals,
    costPct: ratio(totals.cost, totals.revenue),
    shippingPct: ratio(totals.shipping, totals.revenue),
    grossMargin: ratio(totals.grossProfit, totals.revenue),
    promotionPct: ratio(totals.promotion, totals.revenue),
    profitRate: ratio(totals.platformProfit, totals.revenue),
  };
  const page = demoPage(allRows, params.page, params.size);
  return { data: page.data, summary, total: page.total, page: page.page, size: page.size, pages: page.pages };
}

function emptyData() {
  return {
    grand: {},
    peopleSummary: [],
    products: [],
    allStores: [],
    dailyOverall: [],
    dailyByPerson: {},
    dailyByProduct: {},
    dailyByStore: {},
  };
}

async function request(path, options) {
  const response = await fetch(`${apiBase}${path}`, options);
  const contentType = response.headers.get('content-type') || '';
  const body = contentType.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof body === 'object' && body?.error ? body.error : `请求失败（${response.status}）`;
    throw new Error(message);
  }
  return body;
}

export function useProfitData() {
  const data = ref(emptyData());
  const status = ref(null);
  const targets = ref({});
  const loading = ref(false);
  const error = ref('');
  const lastUpdated = ref('');
  const links = ref([]);
  const linkFields = ref([]);
  const linksMeta = ref({ total: 0, page: 1, pages: 0, size: 20 });
  const linksLoading = ref(false);
  const linkDashboard = ref({
    data: [],
    dates: [],
    alerts: { a15: [], a10: [], a5: [] },
    alertCounts: { a15: 0, a10: 0, a5: 0 },
    total: 0,
    page: 1,
    pages: 0,
    size: 20,
  });
  const linkDashboardLoading = ref(false);
  const linkSummary = ref({ data: [], summary: {}, total: 0, page: 1, pages: 0, size: 20 });
  const linkSummaryLoading = ref(false);
  const standards = ref([]);
  const lastDataParams = ref({});

  const availableDates = computed(() => (data.value.dailyOverall || []).map((item) => String(item.date).slice(0, 10)).sort());

  async function loadAll(params = {}) {
    loading.value = true;
    error.value = '';
    lastDataParams.value = { ...params };
    try {
      if (demoMode) {
        const fixture = await loadDemoJson(`dashboard-${demoPeriod}.json`);
        if (!fixture?.success || !fixture?.data) throw new Error('Demo fixture is empty');
        data.value = fixture.data;
        status.value = fixture.status || null;
        targets.value = fixture.targets || {};
        linkFields.value = fixture.linkFields || [];
        standards.value = fixture.standards || [];
        lastUpdated.value = new Date().toLocaleString('zh-CN', { hour12: false });
        return;
      }
      const query = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') query.set(key, value);
      });
      const [dashboard, system, targetResponse, linkFieldsResponse, standardsResponse] = await Promise.all([
        request(`/api/v3/data?${query.toString()}`),
        request('/api/v3/status'),
        request('/api/v3/admin/targets'),
        request('/api/v3/link-fields'),
        request('/api/v3/admin/standards'),
      ]);
      if (!dashboard?.success || !dashboard?.data) throw new Error(dashboard?.error || '看板数据为空');
      data.value = dashboard.data;
      status.value = system;
      targets.value = targetResponse?.data || {};
      linkFields.value = linkFieldsResponse?.fields || [];
      standards.value = standardsResponse?.data || [];
      lastUpdated.value = new Date().toLocaleString('zh-CN', { hour12: false });
    } catch (err) {
      error.value = err.message || '数据加载失败';
    } finally {
      loading.value = false;
    }
  }

  async function refresh() {
    loading.value = true;
    try {
      if (demoMode) {
        await loadAll(lastDataParams.value);
        return;
      }
      await request('/api/v3/refresh', { method: 'POST' });
      await loadAll(lastDataParams.value);
    } finally {
      loading.value = false;
    }
  }

  async function queryLinks(params = {}) {
    if (demoMode) {
      const fixture = await loadDemoJson(`links-${demoPeriod}.json`);
      const rows = (fixture?.data || []).filter((row) => demoRowMatches(row, params));
      return demoPage(rows, params.page, params.size);
    }
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') query.set(key, value);
    });
    const response = await request(`/api/v3/links?${query.toString()}`);
    if (!response?.success) throw new Error(response?.error || '链接数据加载失败');
    return {
      data: response.data || [],
      total: response.total || 0,
      page: response.page || 1,
      pages: response.pages || 0,
      size: response.size || 20,
    };
  }

  async function loadLinks(params = {}) {
    linksLoading.value = true;
    try {
      const page = await queryLinks(params);
      links.value = page.data;
      linksMeta.value = page;
    } finally {
      linksLoading.value = false;
    }
  }

  async function loadLinkDashboard(params = {}) {
    linkDashboardLoading.value = true;
    try {
      if (demoMode) {
        const fixture = await loadDemoJson(`link-dashboard-${demoPeriod}.json`);
        const dates = (fixture?.dates || []).filter((date) => inDemoDateRange(date, params.start, params.end));
        const rows = (fixture?.data || []).filter((row) => demoRowMatches({
          [demoKeys.linkId]: row.linkId,
          [demoKeys.productCode]: row.productCode,
          [demoKeys.title]: row.title,
          [demoKeys.storeName]: row.storeName,
          [demoKeys.person]: row.person,
        }, params)).map((row) => ({
          ...row,
          rates: Object.fromEntries(Object.entries(row.rates || {}).filter(([date]) => dates.includes(date))),
        }));
        const page = demoPage(rows, params.page, params.size);
        linkDashboard.value = {
          ...fixture,
          data: page.data,
          dates,
          total: page.total,
          page: page.page,
          pages: page.pages,
          size: page.size,
        };
        return;
      }
      const query = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') query.set(key, value);
      });
      const response = await request(`/api/v3/link-dashboard?${query.toString()}`);
      if (!response?.success) throw new Error(response?.error || '链接看板加载失败');
      linkDashboard.value = {
        data: response.data || [],
        dates: response.dates || [],
        alerts: response.alerts || { a15: [], a10: [], a5: [] },
        alertCounts: response.alertCounts || { a15: 0, a10: 0, a5: 0 },
        total: response.total || 0,
        page: response.page || 1,
        pages: response.pages || 0,
        size: response.size || 20,
      };
    } finally {
      linkDashboardLoading.value = false;
    }
  }

  async function loadLinkSummary(params = {}) {
    linkSummaryLoading.value = true;
    try {
      if (demoMode) {
        const fixture = await loadDemoJson(`links-${demoPeriod}.json`);
        linkSummary.value = demoLinkSummary(fixture?.data || [], params);
        return;
      }
      const query = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') query.set(key, value);
      });
      const response = await request(`/api/v3/link-summary?${query.toString()}`);
      if (!response?.success) throw new Error(response?.error || '链接汇总加载失败');
      linkSummary.value = {
        data: response.data || [],
        summary: response.summary || {},
        total: response.total || 0,
        page: response.page || 1,
        pages: response.pages || 0,
        size: response.size || 20,
      };
    } finally {
      linkSummaryLoading.value = false;
    }
  }

  async function saveTargets(month, config) {
    if (demoMode) {
      targets.value = { ...targets.value, [month]: config };
      return { success: true, demo: true };
    }
    const response = await request('/api/v3/admin/targets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ month, config }),
    });
    if (!response?.success) throw new Error(response?.error || '目标保存失败');
    targets.value = { ...targets.value, [month]: config };
  }

  async function saveStandard(standard) {
    if (demoMode) {
      const next = { ...standard, id: standard.id || `demo-${Date.now()}` };
      const index = standards.value.findIndex((item) => String(item.id) === String(next.id));
      standards.value = index >= 0 ? standards.value.map((item, itemIndex) => itemIndex === index ? next : item) : [...standards.value, next];
      return { success: true, data: next, demo: true };
    }
    const response = await request('/api/v3/admin/standards', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'save', standard }),
    });
    if (!response?.success) throw new Error(response?.error || '标准保存失败');
    const refreshed = await request('/api/v3/admin/standards');
    standards.value = refreshed?.data || [];
    return response;
  }

  async function deleteStandard(id) {
    if (demoMode) {
      standards.value = standards.value.filter((item) => String(item.id) !== String(id));
      return { success: true, demo: true };
    }
    const response = await request('/api/v3/admin/standards', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'delete', id }),
    });
    if (!response?.success) throw new Error(response?.error || '标准删除失败');
    standards.value = standards.value.filter((item) => String(item.id) !== String(id));
    return response;
  }

  async function submitDelist(payload) {
    if (demoMode) return { success: true, demo: true, message: `Demo mode accepted ${payload?.link_ids?.length || 0} links` };
    return request('/api/delist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  async function submitPromotionAdjust(payload) {
    if (demoMode) return { success: true, demo: true, message: `Demo mode accepted ${payload?.link_ids?.length || 0} links` };
    return request('/api/promotion-adjust', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  return {
    data,
    status,
    targets,
    loading,
    error,
    lastUpdated,
    links,
    linkFields,
    linksMeta,
    linksLoading,
    linkDashboard,
    linkDashboardLoading,
    linkSummary,
    linkSummaryLoading,
    standards,
    availableDates,
    loadAll,
    refresh,
    queryLinks,
    loadLinks,
    loadLinkDashboard,
    loadLinkSummary,
    saveTargets,
    saveStandard,
    deleteStandard,
    submitDelist,
    submitPromotionAdjust,
  };
}
