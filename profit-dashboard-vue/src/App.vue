<template>
  <div class="app-shell">
    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="brand-row">
        <div class="brand-mark">率</div>
        <div v-if="!sidebarCollapsed" class="brand-copy">
          <strong>链接监控</strong>
          <span>Profit workspace</span>
        </div>
        <button class="icon-button sidebar-toggle" aria-label="收起导航" @click="sidebarCollapsed = !sidebarCollapsed">{{ sidebarCollapsed ? '›' : '‹' }}</button>
      </div>

      <nav class="nav-list" aria-label="看板模块">
        <button v-for="item in navItems" :key="item.key" class="nav-item" :class="{ active: activeTab === item.key }" @click="switchTab(item.key)">
          <span class="nav-icon">{{ item.icon }}</span>
          <span v-if="!sidebarCollapsed">{{ item.label }}</span>
        </button>
      </nav>

      <div v-if="!sidebarCollapsed" class="sidebar-footer">
        <div class="status-dot" :class="{ offline: !!error }"></div>
        <div><strong>{{ error ? 'API 异常' : 'API 已连接' }}</strong><span>{{ statusText }}</span></div>
      </div>
    </aside>

    <main class="main-area">
      <header class="topbar">
        <div>
          <p class="breadcrumb">经营分析 / {{ currentNav.label }}</p>
          <h1>{{ currentNav.label }}</h1>
        </div>
        <div class="topbar-actions">
          <div class="sync-copy"><span class="status-dot" :class="{ offline: !!error }"></span>{{ lastUpdated ? `同步于 ${lastUpdated}` : '等待数据同步' }}</div>
          <button class="button secondary" :disabled="loading" @click="refresh">{{ loading ? '同步中…' : '↻ 刷新数据' }}</button>
        </div>
      </header>

      <div v-if="error" class="error-banner"><strong>数据加载失败</strong><span>{{ error }}</span><button class="text-button" @click="loadAll">重试</button></div>
      <div v-if="loading && !hasData" class="loading-state"><div class="loading-spinner"></div><strong>正在从 API 加载看板数据…</strong><span>不会使用本地嵌入数据</span></div>

      <template v-else>
        <section class="toolbar panel-lite">
          <div class="toolbar-title"><span class="toolbar-icon">⌁</span><div><strong>数据日期范围</strong><span>{{ rangeHint }}</span></div></div>
          <div class="toolbar-body">
            <div class="range-controls" aria-label="数据日期筛选">
              <label>数据日期开始 <input v-model="dateStart" type="date" :min="availableDates[0]" :max="availableDates.at(-1)" title="按数据日期筛选开始日期" /></label>
              <span>至</span>
              <label>数据日期结束 <input v-model="dateEnd" type="date" :min="availableDates[0]" :max="availableDates.at(-1)" title="按数据日期筛选结束日期" /></label>
              <button class="range-chip" :class="{ active: rangePreset === 'all' }" @click="setRange('all')">全部</button>
              <button class="range-chip" :class="{ active: rangePreset === 'month' }" @click="setRange('month')">本月</button>
              <button v-for="preset in datePresetOptions" :key="preset.key" class="range-chip" :class="{ active: rangePreset === preset.key }" @click="setRange(preset.key)">{{ preset.label }}</button>
              <span class="range-field-hint">筛选字段：数据日期</span>
            </div>
            <div class="filter-controls" aria-label="维度筛选">
              <label>链接 ID <input v-model="globalFilters.link_ids" placeholder="支持逗号分隔" /></label>
              <label>商品编码 <input v-model="globalFilters.product_code" placeholder="如 FG2" /></label>
              <label>商品名称 <input v-model="globalFilters.product_name" placeholder="输入标题关键词" /></label>
              <label>品牌 <select v-model="globalFilters.brand"><option value="">全部品牌</option><option v-for="brand in brandOptions" :key="brand" :value="brand">{{ brand }}</option></select></label>
              <label>店铺名称 <input v-model="globalFilters.store_name" placeholder="输入店铺名称" /></label>
              <label>负责人 <select v-model="globalFilters.store_person"><option value="">全部负责人</option><option v-for="person in peopleNames" :key="person" :value="person">{{ person }}</option></select></label>
              <button class="button primary compact" :disabled="loading" @click="applyRange">{{ loading ? '加载中…' : '应用' }}</button>
              <button class="button secondary compact" :disabled="loading" @click="clearGlobalFilters">清除筛选</button>
              <button class="button adjust compact" :disabled="!selectedLinks.length" title="对当前已勾选链接调整投产" @click="openPromotionAdjust">📊 调整投产</button>
              <button class="button danger compact" :disabled="!selectedLinks.length" title="下架当前已勾选链接" @click="submitSelectedLinks">📦 产品下架</button>
            </div>
            <div class="creation-filter-row" aria-label="链接创建时间筛选">
              <label>链接创建时间 <select v-model="creationFilter.mode"><option value="age">截至昨日近 N 天</option><option value="custom">指定创建日期</option></select></label>
              <template v-if="creationFilter.mode === 'age'">
                <button v-for="preset in creationPresetOptions" :key="preset.key" type="button" class="range-chip" :class="{ active: creationFilter.days === preset.days }" @click="creationFilter.days = preset.days">{{ preset.label }}</button>
                <label class="creation-days-input">自定义 <input v-model.number="creationFilter.days" type="number" min="1" max="3650" /></label>
              </template>
              <template v-else>
                <label>创建开始 <input v-model="creationFilter.start" type="date" /></label><span>至</span><label>创建结束 <input v-model="creationFilter.end" type="date" /></label>
              </template>
              <span class="filter-state-hint">{{ creationFilterHint }}</span>
            </div>
          </div>
        </section>

        <section v-if="activeTab === 'goals'" class="kpi-grid goal-kpi-grid">
          <article v-for="card in goalKpiCards" :key="card.label" class="kpi-card goal-kpi-card" :class="card.cardClass">
            <template v-if="card.cardClass === 'countdown-card'">
              <div class="countdown-copy">
                <div class="kpi-topline"><span>{{ card.label }}</span></div>
                <strong class="goal-kpi-value" :class="card.valueTone">{{ card.value }}<span class="goal-kpi-unit">{{ card.unit }}</span></strong>
                <small class="goal-kpi-sub"><span v-for="(part, index) in card.subParts" :key="index" :class="part.tone">{{ part.text }}</span></small>
              </div>
              <span class="countdown-icon">{{ card.icon }}</span>
            </template>
            <template v-else>
              <div class="kpi-topline"><span>{{ card.label }}</span><span class="kpi-icon">{{ card.icon }}</span></div>
              <strong class="goal-kpi-value" :class="card.valueTone">{{ card.value }}<span class="goal-kpi-unit">{{ card.unit }}</span></strong>
              <small class="goal-kpi-sub"><span v-for="(part, index) in card.subParts" :key="index" :class="part.tone">{{ part.text }}</span></small>
            </template>
          </article>
        </section>

        <section v-else-if="activeTab !== 'admin' && activeTab !== 'analysis' && activeTab !== 'links' && activeTab !== 'product-management' && activeTab !== 'link-summary'" class="kpi-grid">
          <article v-for="card in kpiCards" :key="card.label" class="kpi-card">
            <div class="kpi-topline"><span>{{ card.label }}</span><span class="kpi-icon">{{ card.icon }}</span></div>
            <strong>{{ card.value }}</strong>
            <small :class="card.tone">{{ card.sub }}</small>
          </article>
        </section>

        <section v-if="activeTab === 'goals'" class="goal-board-grid">
          <section class="panel goal-map-panel">
            <div class="panel-heading"><div><h2>📊 当月目标明细</h2><p>{{ activeMonth }} · 点击节点展开下一层</p></div><span class="panel-badge">{{ formatGoalValue(targetTree.monthTarget, 0) }} 万</span></div>
            <div class="goal-map-scroll">
              <div class="goal-map-flow">
                <button type="button" class="goal-root-node goal-tree-node" :class="{ expanded: goalNodeExpanded('root') }" :aria-expanded="goalNodeExpanded('root')" @click="toggleGoalNode('root')"><span>🎯 月度总目标</span><strong>{{ formatGoalValue(targetTree.monthTarget) }}<small>万</small></strong><em>{{ goalNodeExpanded('root') ? '收起' : '点击展开' }}</em></button>
                <div v-if="goalNodeExpanded('root')" class="goal-map-branches">
                  <svg class="goal-main-connector" viewBox="0 0 44 100" preserveAspectRatio="none" aria-hidden="true"><path d="M0 50 H10 Q20 50 20 40 V25 H44 M20 60 V75 H44" /></svg>
                  <div class="goal-map-branch brand-branch">
                    <button type="button" class="goal-branch-node goal-tree-node" :class="{ expanded: goalNodeExpanded('brand') }" :aria-expanded="goalNodeExpanded('brand')" @click="toggleGoalNode('brand')"><span>🏷 品牌目标</span><strong>{{ formatGoalValue(targetTree.brandTotal) }}<small>万</small></strong><small>占比 {{ formatPercent(targetTree.brandShare) }}</small><em>{{ goalNodeExpanded('brand') ? '收起' : '点击展开' }}</em></button>
                    <span v-if="goalNodeExpanded('brand')" class="goal-branch-connector" aria-hidden="true"></span>
                    <div v-if="goalNodeExpanded('brand')" class="goal-leaves brand-leaves"><div v-for="item in targetTree.brands" :key="item.name" class="goal-leaf brand-leaf"><span>{{ item.name }}</span><strong>{{ formatGoalValue(item.value) }}</strong><small>万</small></div></div>
                  </div>
                  <div class="goal-map-branch person-branch">
                    <button type="button" class="goal-branch-node person-node goal-tree-node" :class="{ expanded: goalNodeExpanded('person') }" :aria-expanded="goalNodeExpanded('person')" @click="toggleGoalNode('person')"><span>👤 负责人目标</span><strong>{{ formatGoalValue(targetTree.personTotal) }}<small>万</small></strong><small>占比 {{ formatPercent(targetTree.personShare) }}</small><em>{{ goalNodeExpanded('person') ? '收起' : '点击展开' }}</em></button>
                    <span v-if="goalNodeExpanded('person')" class="goal-branch-connector" aria-hidden="true"></span>
                    <div v-if="goalNodeExpanded('person')" class="goal-leaves person-leaves"><div v-for="item in targetTree.persons" :key="item.name" class="goal-leaf person-leaf"><span>{{ item.name }}</span><strong>{{ formatGoalValue(item.value) }}</strong><small>万</small></div></div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section class="panel goal-alert-panel">
            <div class="panel-heading"><div><h2>⚠️ 目标进度预警建议</h2><p>按当前日期范围与 {{ activeMonth }} 目标对比</p></div><span class="panel-badge">{{ goalAlerts.length }} 条</span></div>
            <div class="goal-alert-list">
              <div v-for="alert in goalAlerts" :key="alert.key" class="goal-alert" :class="alert.severity"><span class="goal-alert-icon">{{ alert.icon }}</span><div><b>{{ alert.name }}</b><span>{{ alert.message }}</span><strong v-if="alert.rate !== null">{{ alert.rate.toFixed(1) }}%</strong><span>{{ alert.suffix }}</span></div></div>
            </div>
          </section>
        </section>

        <section v-if="activeTab === 'goals'" class="content-grid goals-grid">
          <ChartPanel title="每日收入趋势" subtitle="按当前数据范围汇总" :options="revenueOption" :empty="!filteredDays.length" :height="318" />
          <section class="panel target-panel">
            <div class="panel-heading"><div><h2>目标进度</h2><p>{{ activeMonth }} · 目标来自 admin_targets</p></div><button class="text-button" @click="switchTab('admin')">配置目标 →</button></div>
            <div class="target-summary"><strong>{{ formatTargetWan(activeTarget.monthTarget) }}</strong><span>月度销售目标（万元）</span></div>
            <div v-for="row in goalRows" :key="row.name" class="progress-row"><div><span>{{ row.name }}</span><b>{{ row.actual.toFixed(1) }} / {{ row.target ? row.target.toFixed(1) : '—' }} 万</b></div><div class="progress-track"><i :style="{ width: `${Math.min(row.rate, 100)}%` }" :class="progressClass(row.rate)"></i></div><small>{{ row.target ? `${row.rate.toFixed(1)}% 完成` : '未配置目标' }}</small></div>
            <div v-if="!goalRows.length" class="empty-inline">API 暂无负责人目标数据</div>
          </section>
        </section>

        <section v-if="activeTab === 'goals'" class="content-grid goal-brand-detail-grid">
          <ChartPanel title="🏷️ 品牌目标达成进度预警" subtitle="当前范围实际收入 / 品牌目标" :options="goalBrandOption" :empty="!brandRows.length" :height="300" />
          <section class="panel table-panel goal-brand-table-panel"><div class="panel-heading"><div><h2>🏷️ 品牌目标明细表</h2><p>目标、实际、完成率与差距 · 数据来自 API</p></div></div><DataTable :columns="brandGoalColumns" :rows="brandGoalRows" /></section>
        </section>

        <section v-if="activeTab === 'goals'" class="content-grid goal-person-detail-grid">
          <ChartPanel title="👤 负责人目标达成进度预警" subtitle="当前范围实际收入 / 负责人目标" :options="goalPersonOption" :empty="!goalRows.length" :height="300" />
          <section class="panel table-panel goal-person-table-panel"><div class="panel-heading"><div><h2>📋 负责人目标明细表</h2><p>目标、实际、完成率与差距 · 数据来自 API</p></div></div><DataTable :columns="personGoalColumns" :rows="personGoalRows" /></section>
        </section>

        <section v-else-if="activeTab === 'overview'" class="overview-page">
          <section class="panel overview-insight">
            <strong>💡 负责人总览:</strong>
            <span v-for="item in overviewInsights" :key="item.key" class="overview-insight-item"><span>{{ item.icon }}</span>{{ item.label }} <b :class="item.tone">{{ item.value }}</b>{{ item.suffix }}</span>
          </section>

          <section class="content-grid overview-daily-grid">
            <ChartPanel title="📊 每日收入波动" subtitle="收入与利润率 · 当前日期范围" :options="overviewRevenueOption" :empty="!filteredDays.length" :height="420" />
            <ChartPanel title="📈 每日利润率波动" subtitle="整体利润率与负责人趋势" :options="overviewProfitRateOption" :empty="!filteredDays.length" :height="420" @chart-click="focusProfitRateLine">
              <template #actions><span v-if="focusedProfitRateSeries" class="overview-focus-state">已聚焦：{{ focusedProfitRateSeries }}</span><button type="button" class="overview-toggle" :class="{ active: showPersonLines }" @click="showPersonLines = !showPersonLines">{{ showPersonLines ? '👥 隐藏分负责人' : '👤 显示分负责人' }}</button></template>
            </ChartPanel>
          </section>

          <section class="content-grid overview-pair-grid">
            <ChartPanel title="各负责人收入 vs 利润率对比" subtitle="当前日期范围" :options="personRevenueOption" :empty="!peopleRows.length" :height="300" />
            <ChartPanel title="毛利率 vs 利润率对比(负责人)" subtitle="当前日期范围" :options="personMarginOption" :empty="!peopleRows.length" :height="300" />
          </section>

          <section class="content-grid overview-pair-grid">
            <ChartPanel title="推广费占比排行(负责人)" subtitle="当前日期范围 · 高于 35% 重点关注" :options="personPromotionOption" :empty="!peopleRows.length" :height="300" />
            <section class="panel advice-panel">
              <div class="panel-heading"><div><h2>💡 经营分析建议</h2><p>根据当前日期范围自动生成</p></div></div>
              <div class="advice-list">
                <article v-for="item in overviewAdvice" :key="item.key" class="advice-item"><span class="advice-icon">{{ item.icon }}</span><div class="advice-content"><strong :style="{ color: item.color }">{{ item.title }}</strong><div class="advice-bar"><i :style="{ width: `${item.bar}%`, background: item.color }"></i></div><p>{{ item.description }}</p></div></article>
              </div>
            </section>
          </section>

          <section class="panel table-panel wide overview-table-panel"><div class="panel-heading"><div><h2>📋 负责人汇总表</h2><p>收入、成本、快递、毛利、推广费与平台利润 · 数据来自 API</p></div></div><DataTable :columns="personOverviewColumns" :rows="personOverviewRows" /></section>
        </section>

        <section v-else-if="activeTab === 'stores'" class="store-detail-page">
          <section class="panel overview-insight store-insight">
            <strong>💡 店铺洞察:</strong>
            <span v-for="item in storeInsights" :key="item.key" class="overview-insight-item"><span>{{ item.icon }}</span>{{ item.label }} <b :class="item.tone">{{ item.value }}</b>{{ item.suffix }}</span>
          </section>

          <section class="content-grid store-detail-grid">
            <ChartPanel title="各店铺收入排行" subtitle="Top 15 · 当前日期范围" :options="storeRevenueOption" :empty="!storeRows.length" :height="420" />
            <ChartPanel title="店铺毛利率 vs 利润率象限" subtitle="气泡大小代表当前范围收入" :options="storeQuadrantOption" :empty="!storeQuadrantRows.length" :height="420" />
          </section>

          <section class="content-grid store-detail-grid store-detail-small-grid">
            <ChartPanel title="店铺推广费占比对比" subtitle="Top 15 店铺 · 毛利率与推广占比" :options="storePromotionOption" :empty="!storeRows.length" :height="330" />
            <ChartPanel title="利润率最低店铺" subtitle="Top 10 亏损店铺" :options="storeLossOption" :empty="!storeLossRows.length" :height="330" />
          </section>

          <section class="panel table-panel wide store-table-panel">
            <div class="panel-heading"><div><h2>📋 全部店铺明细表</h2><p>按收入排序 · {{ storeRows.length }} 家店铺 · 数据来自 API</p></div></div>
            <DataTable :columns="storeColumns" :rows="storeRows" />
          </section>
        </section>

        <section v-else-if="activeTab === 'products'" class="product-detail-page">
          <section class="panel overview-insight product-insight">
            <strong>💡 商品洞察:</strong>
            <span v-for="item in productInsights" :key="item.key" class="overview-insight-item"><span>{{ item.icon }}</span>{{ item.label }} <b :class="item.tone">{{ item.value }}</b>{{ item.suffix }}</span>
          </section>

          <section class="content-grid product-detail-grid">
            <ChartPanel title="Top 15 商品收入排行" subtitle="收入与平台利润 · 当前日期范围" :options="productTopOption" :empty="!productRows.length" :height="420" />
            <section class="panel product-advice-panel">
              <div class="panel-heading"><div><h2>💡 商品经营建议</h2><p>根据当前日期范围自动生成</p></div></div>
              <div class="product-advice-list">
                <article v-for="item in productAdvice" :key="item.key" class="advice-item"><span class="advice-icon">{{ item.icon }}</span><div class="advice-content"><strong :style="{ color: item.color }">{{ item.title }}</strong><p>{{ item.description }}</p></div></article>
              </div>
            </section>
          </section>

          <ChartPanel class="product-profit-range-panel" title="商品 TOP 10 每日利润率波动" subtitle="按当前日期范围收入排序，展示各商品每日利润率" :options="productProfitRangeOption" :empty="!productProfitRangeRows.length" :height="420" @chart-click="focusProductProfitLine">
            <template #actions><span v-if="focusedProductProfitSeries" class="overview-focus-state product-focus-state">已聚焦：{{ focusedProductProfitSeries }}</span></template>
          </ChartPanel>

          <section class="panel table-panel wide product-table-panel">
            <div class="panel-heading"><div><h2>📋 全部商品明细（按收入排序）</h2><p>{{ productRows.length }} 个商品编码 · 数据来自 API</p></div></div>
            <DataTable :columns="productColumns" :rows="productRows" />
          </section>
        </section>

        <section v-else-if="activeTab === 'analysis'" class="analysis-page">
          <section class="panel analysis-header">
            <div class="panel-heading"><div><h2>📐 多维度数据分析</h2><p>按全局筛选结果聚合，标准来自管理中台，可切换维度与指标</p></div><span class="panel-badge">{{ analysisRows.length }} 个分析对象</span></div>
            <div class="analysis-controls">
              <label>分析维度 <select v-model="analysisDimension"><option value="brand">品牌</option><option value="product">商品</option><option value="store">店铺</option><option value="person">负责人</option></select></label>
              <label>核心指标 <select v-model="analysisMetric"><option value="profitRate">利润率</option><option value="grossMargin">毛利率</option><option value="promotionPct">推广占比</option><option value="revenue">收入</option><option value="orders">单量</option></select></label>
              <span class="analysis-filter-copy">当前周期：{{ rangeHint }} · {{ creationFilterHint }}</span>
            </div>
          </section>
          <section class="content-grid analysis-summary-grid">
            <article class="panel analysis-stat"><span>分析对象</span><strong>{{ analysisRows.length }}</strong><small>{{ analysisDimensionLabel }}</small></article>
            <article class="panel analysis-stat"><span>达标对象</span><strong class="positive">{{ analysisStatusCounts.pass }}</strong><small>满足后台标准</small></article>
            <article class="panel analysis-stat"><span>关注对象</span><strong class="warning">{{ analysisStatusCounts.watch }}</strong><small>需要运营跟进</small></article>
            <article class="panel analysis-stat"><span>不达标对象</span><strong class="negative">{{ analysisStatusCounts.fail }}</strong><small>优先处理</small></article>
          </section>
          <section class="panel table-panel analysis-table-panel">
            <div class="panel-heading"><div><h2>📊 条件分析结果</h2><p>每个对象同时展示实际指标、标准值和执行状态</p></div><button class="button secondary compact" @click="switchTab('admin')">配置标准 →</button></div>
            <DataTable :columns="analysisColumns" :rows="analysisRows" />
          </section>
        </section>

        <section v-else-if="activeTab === 'links'" class="link-section">
          <section class="panel link-detail-panel">
            <div class="link-detail-header">
              <button type="button" class="link-detail-title" :aria-expanded="linkDetailExpanded" title="点击收起/展开" @click="linkDetailExpanded = !linkDetailExpanded">
                <span class="toggle-icon">{{ linkDetailExpanded ? '▼' : '▶' }}</span>
                <span>📊 链接明细</span>
                <small>({{ linkDashboardMeta.total.toLocaleString() }}条)</small>
              </button>
              <div class="link-detail-controls">
                <input v-model="linkQuery.search" class="link-search-input" placeholder="🔍 搜索链接ID/编码/标题..." @input="scheduleLinkRefresh" @keyup.enter="refreshLinkViews" />
                <input v-model="dateStart" type="date" :min="availableDates[0]" :max="availableDates.at(-1)" title="开始日期" @change="normalizeLinkDateRange" />
                <span>至</span>
                <input v-model="dateEnd" type="date" :min="availableDates[0]" :max="availableDates.at(-1)" title="结束日期" @change="normalizeLinkDateRange" />
                <span>每页</span>
                <select v-model.number="linkQuery.size" @change="refreshLinkViews"><option :value="20">20条</option><option :value="50">50条</option><option :value="100">100条</option></select>
                <div class="link-pager link-pager-top">
                  <button type="button" :disabled="linkDashboardMeta.page <= 1 || linkDashboardLoading" aria-label="第一页" @click="fetchLinkDashboard(1)">«</button>
                  <button type="button" :disabled="linkDashboardMeta.page <= 1 || linkDashboardLoading" aria-label="上一页" @click="fetchLinkDashboard(linkDashboardMeta.page - 1)">‹</button>
                  <span>{{ linkDashboardMeta.page }} / {{ linkDashboardMeta.pages || 1 }}</span>
                  <button type="button" :disabled="linkDashboardMeta.page >= linkDashboardMeta.pages || linkDashboardLoading" aria-label="下一页" @click="fetchLinkDashboard(linkDashboardMeta.page + 1)">›</button>
                  <button type="button" :disabled="linkDashboardMeta.page >= linkDashboardMeta.pages || linkDashboardLoading" aria-label="最后一页" @click="fetchLinkDashboard(linkDashboardMeta.pages || 1)">»</button>
                </div>
              </div>
            </div>
            <div v-if="linkDetailExpanded" class="link-detail-content">
              <div class="link-alerts">
                <template v-for="group in linkAlertGroups" :key="group.key">
                  <section v-if="group.items.length" class="link-alert-group" :class="group.tone">
                    <button type="button" class="link-alert-header" :aria-expanded="linkAlertOpen[group.key]" @click="toggleLinkAlert(group.key)"><span>{{ group.icon }} {{ group.label }} <small>({{ group.count }}条)</small></span><span>{{ linkAlertOpen[group.key] ? '▼' : '▶' }}</span></button>
                    <div v-show="linkAlertOpen[group.key]" class="link-alert-list">
                      <button v-for="item in group.items" :key="item.id" type="button" class="link-alert-item" @click="selectLinkAlert(item)"><span class="alert-days">{{ item.days }}天</span><code>{{ item.id }}</code><span>{{ item.code }}</span><em>{{ item.store }}</em></button>
                      <div v-if="group.count > group.items.length" class="link-alert-more">...还有{{ group.count - group.items.length }}条</div>
                    </div>
                  </section>
                </template>
                <div v-if="!linkDashboardLoading && !linkAlertGroups.some((group) => group.items.length)" class="link-alert-empty">当前日期范围内没有连续亏损预警</div>
              </div>
              <div class="link-detail-table-scroll">
                <table class="link-detail-table">
                  <thead><tr><th v-for="column in linkDashboardFixedColumns" :key="column.key" :class="`link-fixed-${column.key}`">{{ column.label }}</th><th v-for="date in linkDashboardDates" :key="date" class="link-date-column">{{ date.slice(5) }}</th></tr></thead>
                  <tbody>
                    <tr v-for="row in linkDashboardRows" :key="row.linkId"><td v-for="column in linkDashboardFixedColumns" :key="column.key" :class="`link-fixed-${column.key}`" :title="row[column.key]">{{ row[column.key] || '—' }}</td><td v-for="date in linkDashboardDates" :key="`${row.linkId}-${date}`" class="link-rate-cell" :class="linkRateTone(row.rates?.[date])">{{ formatLinkRate(row.rates?.[date]) }}</td></tr>
                    <tr v-if="!linkDashboardLoading && !linkDashboardRows.length"><td :colspan="linkDashboardFixedColumns.length + linkDashboardDates.length" class="empty-cell">暂无链接数据</td></tr>
                  </tbody>
                </table>
              </div>
              <div class="link-pager link-pager-bottom">
                <button type="button" :disabled="linkDashboardMeta.page <= 1 || linkDashboardLoading" @click="fetchLinkDashboard(1)">«</button>
                <button type="button" :disabled="linkDashboardMeta.page <= 1 || linkDashboardLoading" @click="fetchLinkDashboard(linkDashboardMeta.page - 1)">‹</button>
                <span>第 {{ linkDashboardMeta.page }} / {{ linkDashboardMeta.pages || 1 }} 页</span>
                <button type="button" :disabled="linkDashboardMeta.page >= linkDashboardMeta.pages || linkDashboardLoading" @click="fetchLinkDashboard(linkDashboardMeta.page + 1)">›</button>
                <button type="button" :disabled="linkDashboardMeta.page >= linkDashboardMeta.pages || linkDashboardLoading" @click="fetchLinkDashboard(linkDashboardMeta.pages || 1)">»</button>
              </div>
            </div>
          </section>

          <section class="panel table-panel"><div class="table-toolbar"><span>{{ linksLoading ? '查询中…' : `第 ${linksMeta.page} / ${linksMeta.pages || 1} 页` }}</span><div><button class="button secondary compact" :disabled="linksMeta.page <= 1 || linksLoading" @click="fetchLinks(linksMeta.page - 1)">上一页</button><button class="button secondary compact" :disabled="linksMeta.page >= linksMeta.pages || linksLoading" @click="fetchLinks(linksMeta.page + 1)">下一页</button></div></div><div class="table-scroll link-data-table-scroll"><table><thead><tr><th><input type="checkbox" :checked="allLinksSelected" @change="toggleAllLinks" /></th><th v-for="column in linkColumns" :key="column.key">{{ column.label }}</th></tr></thead><tbody><tr v-for="row in links" :key="`${row['链接id']}-${row['数据日期']}`"><td><input v-model="selectedLinks" type="checkbox" :value="row['链接id']" /></td><td v-for="column in linkColumns" :key="column.key" :class="column.tone">{{ formatLinkValue(row[column.key], column.key, row) }}</td></tr><tr v-if="!linksLoading && !links.length"><td :colspan="linkColumns.length + 1" class="empty-cell">暂无链接数据</td></tr></tbody></table></div></section>
        </section>

        <!-- 商品管理是链接明细逐日数据表的独立克隆入口，复用同一数据源和操作处理器。 -->
        <section v-else-if="activeTab === 'product-management'" class="product-management-page">
          <section class="panel product-management-header">
            <div class="panel-heading">
              <div><h2>📋 商品管理明细表</h2><p>一行一日的商品经营明细 · 数据来自链接明细 API</p></div>
              <span class="panel-badge">{{ linksMeta.total.toLocaleString() }} 行</span>
            </div>
            <div class="link-data-toolbar product-management-toolbar">
              <span class="link-toolbar-icon">📅</span>
              <input v-model="linkDataDateStart" type="date" :min="availableDates[0]" :max="availableDates.at(-1)" title="开始日期" @change="normalizeLinkDataDateRange" />
              <span>至</span>
              <input v-model="linkDataDateEnd" type="date" :min="availableDates[0]" :max="availableDates.at(-1)" title="结束日期" @change="normalizeLinkDataDateRange" />
              <span>链接 ID</span>
              <input v-model="linkDataLinkIds" class="link-id-filter" placeholder="支持逗号分隔" title="输入链接 ID 筛选，支持逗号分隔多个" @keyup.enter="applyLinkFilters" />
              <span>每页</span>
              <select v-model.number="linkQuery.size" @change="refreshLinkData"><option :value="10">10 条</option><option :value="20">20 条</option><option :value="50">50 条</option></select>
              <span>字段</span>
              <div class="link-column-picker" @click.stop>
                <button type="button" class="button secondary compact" @click="linkColumnsOpen = !linkColumnsOpen">⚙ 选择字段</button>
                <div v-if="linkColumnsOpen" class="link-column-menu">
                  <strong>显示字段</strong>
                  <label v-for="column in linkColumnOptions" :key="column.key"><input type="checkbox" :checked="visibleLinkColumnKeys === null || visibleLinkColumnKeys.includes(column.key)" @change="toggleLinkColumn(column.key, $event.target.checked)" /> {{ column.label }}</label>
                  <div class="link-column-actions"><button type="button" @click="selectAllLinkColumns(true)">全选</button><button type="button" @click="selectAllLinkColumns(false)">全不选</button></div>
                </div>
              </div>
              <button type="button" class="filter-add-btn" title="新增筛选维度" @click="addLinkFilter">＋</button>
              <div class="filter-rows-wrap">
                <div v-for="(filter, index) in linkFilters" :key="filter.id" class="link-filter-row">
                  <select v-model="filter.field" class="link-filter-field" @change="onLinkFilterFieldChange(filter)"><option value="">— 选择字段 —</option><option v-for="field in linkFilterFields" :key="field.key" :value="field.key">{{ field.label }}</option></select>
                  <select v-if="linkFilterType(filter) !== 'text'" v-model="filter.op" class="link-filter-op" @change="normalizeLinkFilterOperator(filter)"><option value="between">区间</option><option value="gte">≥</option><option value="lte">≤</option></select>
                  <select v-if="filter.field === '品牌'" v-model="filter.v1" class="link-filter-value link-brand-value" @change="applyLinkFilters"><option value="">选择品牌</option><option v-for="brand in brandOptions" :key="brand" :value="brand">{{ brand }}</option></select>
                  <input v-else v-model="filter.v1" :type="linkFilterInputType(filter)" class="link-filter-value" :placeholder="linkFilterPlaceholder(filter)" @keyup.enter="applyLinkFilters" />
                  <input v-if="linkFilterUsesSecondValue(filter)" v-model="filter.v2" :type="linkFilterInputType(filter)" class="link-filter-value" placeholder="上限" @keyup.enter="applyLinkFilters" />
                  <button type="button" class="filter-remove-btn" title="移除此条件" @click="removeLinkFilter(index)">×</button>
                </div>
              </div>
              <button v-if="linkFilters.length" type="button" class="filter-confirm" title="应用筛选" @click="applyLinkFilters">✅</button>
              <button v-if="linkFilters.length" type="button" class="filter-clear" title="清除筛选" @click="clearLinkFilters">✕</button>
              <span v-if="linkFilterSummary" class="filter-result">{{ linkFilterSummary }}</span>
              <button type="button" class="button primary compact" :disabled="linksLoading" @click="applyLinkFilters">🔎 查询</button>
              <button type="button" class="button secondary compact" @click="exportLinksCsv">📥 导出 CSV</button>
              <button type="button" class="button secondary compact" :disabled="linksLoading" @click="refreshLinkData">🔄 刷新</button>
            </div>
          </section>

          <section class="panel table-panel product-management-table-panel">
            <div class="table-toolbar"><span>{{ linksLoading ? '查询中…' : `第 ${linksMeta.page} / ${linksMeta.pages || 1} 页` }}</span><div><button class="button secondary compact" :disabled="linksMeta.page <= 1 || linksLoading" @click="fetchLinks(linksMeta.page - 1)">上一页</button><button class="button secondary compact" :disabled="linksMeta.page >= linksMeta.pages || linksLoading" @click="fetchLinks(linksMeta.page + 1)">下一页</button></div></div>
            <div class="table-scroll link-data-table-scroll"><table><thead><tr><th><input type="checkbox" :checked="allLinksSelected" @change="toggleAllLinks" /></th><th v-for="column in linkColumns" :key="column.key">{{ column.label }}</th></tr></thead><tbody><tr v-for="row in links" :key="`${row['链接id']}-${row['数据日期']}`"><td><input v-model="selectedLinks" type="checkbox" :value="row['链接id']" /></td><td v-for="column in linkColumns" :key="column.key" :class="column.tone">{{ formatLinkValue(row[column.key], column.key, row) }}</td></tr><tr v-if="!linksLoading && !links.length"><td :colspan="linkColumns.length + 1" class="empty-cell">暂无商品数据</td></tr></tbody></table></div>
          </section>
        </section>

        <section v-else-if="activeTab === 'link-summary'" class="link-summary-page">
          <section class="panel link-summary-header">
            <div class="panel-heading"><div><h2>📊 链接汇总数据板</h2><p>按链接 ID 聚合 · 金额求和 · 百分占比按当前周期重新计算</p></div><span class="panel-badge">{{ linkSummaryMeta.total.toLocaleString() }} 个链接</span></div>
            <div class="link-summary-kpis">
              <article><span>汇总链接数</span><strong>{{ linkSummaryTotals.links.toLocaleString() }}</strong><small>{{ linkSummaryTotals.rows.toLocaleString() }} 行明细</small></article>
              <article><span>周期收入</span><strong>{{ formatSummaryWan(linkSummaryTotals.revenue) }}<em>万</em></strong><small>{{ linkSummaryTotals.dataDays }} 天</small></article>
              <article><span>货品成本</span><strong>{{ formatSummaryWan(linkSummaryTotals.cost) }}<em>万</em></strong><small>成本占比 {{ formatSummaryPercent(linkSummaryTotals.costPct) }}</small></article>
              <article><span>毛利</span><strong>{{ formatSummaryWan(linkSummaryTotals.grossProfit) }}<em>万</em></strong><small>毛利率 {{ formatSummaryPercent(linkSummaryTotals.grossMargin) }}</small></article>
              <article><span>推广费</span><strong>{{ formatSummaryWan(linkSummaryTotals.promotion) }}<em>万</em></strong><small>推广占比 {{ formatSummaryPercent(linkSummaryTotals.promotionPct) }}</small></article>
              <article><span>平台利润</span><strong :class="linkSummaryTotals.platformProfit >= 0 ? 'positive' : 'negative'">{{ formatSummaryWan(linkSummaryTotals.platformProfit) }}<em>万</em></strong><small>利润率 {{ formatSummaryPercent(linkSummaryTotals.profitRate) }}</small></article>
            </div>
          </section>

          <section class="content-grid link-summary-chart-grid">
            <ChartPanel title="链接收入排行" subtitle="Top 15 · 当前日期范围" :options="linkSummaryRevenueOption" :empty="!linkSummaryRows.length" :height="360" />
            <ChartPanel title="链接利润率与推广占比" subtitle="Top 15 · 按收入排序" :options="linkSummaryRateOption" :empty="!linkSummaryRows.length" :height="360" />
          </section>

          <section class="panel table-panel wide link-summary-table-panel">
            <div class="panel-heading"><div><h2>📋 链接 ID 聚合明细</h2><p>{{ linkSummaryTotals.firstDate || '—' }} 至 {{ linkSummaryTotals.lastDate || '—' }} · 比例字段按汇总后的分子 / 收入重新计算</p></div><span class="panel-badge">第 {{ linkSummaryMeta.page }} / {{ linkSummaryMeta.pages || 1 }} 页</span></div>
            <div class="link-summary-toolbar"><label>搜索链接 <input v-model="linkSummaryQuery.search" placeholder="链接 ID / 商品编码 / 店铺" @keyup.enter="fetchLinkSummary(1)" /></label><label>每页 <select v-model.number="linkSummaryQuery.size" @change="fetchLinkSummary(1)"><option :value="20">20 条</option><option :value="50">50 条</option><option :value="100">100 条</option></select></label><button type="button" class="button primary compact" :disabled="linkSummaryLoading" @click="fetchLinkSummary(1)">{{ linkSummaryLoading ? '查询中…' : '🔎 查询' }}</button><button type="button" class="button secondary compact" :disabled="linkSummaryLoading" @click="fetchLinkSummary(1)">🔄 刷新</button><span class="link-summary-sort-hint">{{ linkSummarySortHint }}</span><div class="link-pager"><button type="button" :disabled="linkSummaryMeta.page <= 1 || linkSummaryLoading" @click="fetchLinkSummary(linkSummaryMeta.page - 1)">上一页</button><button type="button" :disabled="linkSummaryMeta.page >= linkSummaryMeta.pages || linkSummaryLoading" @click="fetchLinkSummary(linkSummaryMeta.page + 1)">下一页</button></div></div>
            <DataTable :columns="linkSummaryColumns" :rows="linkSummaryRows" :sortable="true" :sort-key="linkSummarySort.key" :sort-order="linkSummarySort.order" :row-clickable="true" row-key="linkId" :expanded-key="expandedLinkSummaryId" @sort="changeLinkSummarySort" @row-click="toggleLinkSummaryRow">
              <template #expanded="{ row }">
                <div class="link-summary-expanded">
                  <div class="link-summary-expanded-heading"><div><strong>链接 {{ row.linkId }} · 每日明细</strong><span>{{ row.productCode || '暂无编码' }} · {{ row.person || '未分配负责人' }}</span></div><small>当前链接筛选已同步到其他看板</small></div>
                  <div v-if="linkSummaryDailyLoading" class="link-summary-daily-state">正在加载该链接的每日数据…</div>
                  <div v-else-if="linkSummaryDailyError" class="link-summary-daily-state error">{{ linkSummaryDailyError }}</div>
                  <div v-else-if="!linkSummaryDailyRows.length" class="link-summary-daily-state">当前日期范围内暂无每日明细</div>
                  <div v-else class="table-scroll link-summary-daily-scroll">
                    <table class="link-summary-daily-table"><thead><tr><th v-for="column in linkSummaryDailyColumns" :key="column.key">{{ column.label }}</th></tr></thead><tbody><tr v-for="dailyRow in linkSummaryDailyRows" :key="`${dailyRow['链接id']}-${dailyRow['数据日期']}`"><td v-for="column in linkSummaryDailyColumns" :key="column.key" :class="column.tone">{{ formatLinkValue(dailyRow[column.key], column.key, dailyRow) }}</td></tr></tbody></table>
                  </div>
                </div>
              </template>
            </DataTable>
          </section>
        </section>

        <section v-else-if="activeTab === 'cost'" class="content-grid">
          <ChartPanel title="整体成本结构" subtitle="当前范围" :options="costOption" :empty="!hasData" :height="340" />
          <ChartPanel title="负责人成本结构" subtitle="收入、成本、快递与推广费" :options="costPersonOption" :empty="!peopleRows.length" :height="340" />
          <ChartPanel title="推广费 vs 平台利润" subtitle="当前范围" :options="promoProfitOption" :empty="!peopleRows.length" :height="320" />
          <ChartPanel title="推广效率" subtitle="每 1 元推广费带来的收入" :options="promoEfficiencyOption" :empty="!peopleRows.length" :height="320" />
        </section>

        <section v-else class="admin-section">
          <section class="panel admin-header"><div><h2>管理中台</h2><p>集中维护链接维度的品牌、商品编码、商品名称与运营判断标准。</p></div></section>
          <section class="panel standards-panel">
            <div class="panel-heading"><div><h2>🔗 链接设置</h2><p>通过“新增筛选维度”配置链接运营判断线，并为每条设置保存明细筛选条件</p></div><button class="button primary compact" @click="addStandardRow">＋ 新增设置</button></div>
            <div class="standards-table-scroll">
              <table class="standards-table">
                <thead><tr><th>启用</th><th>备注</th><th>条件筛选</th><th>操作</th></tr></thead>
                <tbody>
                  <template v-for="row in standardRows" :key="row._key">
                    <tr>
                      <td><input v-model="row.enabled" type="checkbox" /></td>
                      <td><input v-model="row.note" placeholder="说明" /></td>
                      <td class="standard-filter-cell"><button type="button" class="standard-filter-toggle" @click="row.filterConfig.open = !row.filterConfig.open">{{ row.filterConfig.open ? '收起条件' : '配置条件' }}</button><small v-if="standardFilterSummary(row)">{{ standardFilterSummary(row) }}</small></td>
                      <td><button class="text-button" :disabled="row.saving" @click="saveStandardRow(row)">{{ row.saving ? '保存中' : '保存' }}</button><button class="text-button danger-text" @click="removeStandardRow(row)">删除</button></td>
                    </tr>
                    <tr v-if="row.filterConfig.open" class="standard-filter-editor-row">
                      <td colspan="4">
                        <div class="standard-filter-editor">
                          <div class="standard-filter-toolbar">
                            <button type="button" class="filter-add-btn" title="新增筛选维度" @click="addStandardFilter(row)">＋</button>
                          </div>
                          <div v-if="row.filterConfig.filters.length" class="standard-filter-rows">
                            <div v-for="(filter, index) in row.filterConfig.filters" :key="filter.id" class="standard-filter-row">
                              <select v-model="filter.field" class="link-filter-field" @change="onStandardFilterFieldChange(row, filter); queryStandardRow(row)"><option value="">— 选择字段 —</option><option v-for="field in linkFilterFields" :key="field.key" :value="field.key">{{ field.label }}</option></select>
                              <select v-if="standardFilterType(row, filter) !== 'text'" v-model="filter.op" class="link-filter-op" @change="normalizeStandardFilterOperator(row, filter); queryStandardRow(row)"><option value="between">区间</option><option value="gte">≥</option><option value="lte">≤</option></select>
                              <select v-if="filter.field === '品牌'" v-model="filter.v1" class="link-filter-value standard-brand-value" @change="queryStandardRow(row)"><option value="">选择品牌</option><option v-for="brand in brandOptions" :key="brand" :value="brand">{{ brand }}</option></select>
                              <input v-else v-model="filter.v1" :type="standardFilterInputType(row, filter)" class="link-filter-value" :placeholder="standardFilterPlaceholder(row, filter)" @change="queryStandardRow(row)" @keyup.enter="queryStandardRow(row)" />
                              <input v-if="standardFilterUsesSecondValue(row, filter)" v-model="filter.v2" :type="standardFilterInputType(row, filter)" class="link-filter-value" placeholder="上限" @change="queryStandardRow(row)" @keyup.enter="queryStandardRow(row)" />
                              <button type="button" class="filter-remove-btn" title="移除此条件" @click="removeStandardFilter(row, index)">×</button>
                            </div>
                          </div>
                          <div class="standard-filter-aggregation-note">聚合口径：先筛选链接创建时间与其他维度，再按链接 ID + 负责人汇总；利润率 = 平台利润合计 ÷ 收入合计</div>
                          <div class="standard-filter-result"><span v-if="standardFilterSummary(row)">{{ standardFilterSummary(row) }}</span><span v-else>未配置明细筛选条件</span><span v-if="row.filterConfig.message"> · {{ row.filterConfig.message }}</span></div>
                          <div v-if="row.filterConfig.previewRows.length" class="standard-filter-preview"><span>已按链接 ID + 负责人聚合：</span><strong>{{ row.filterConfig.previewMeta.total.toLocaleString() }} 组</strong><small>当前页 {{ row.filterConfig.previewRows.length }} 组，可在保存后复用这组筛选条件</small></div>
                        </div>
                      </td>
                    </tr>
                  </template>
                  <tr v-if="!standardRows.length"><td colspan="4" class="empty-cell">暂无设置，点击右上角新增</td></tr>
                </tbody>
              </table>
            </div>
          </section>
        </section>
      </template>
    </main>

    <div v-if="adjustModalOpen" class="modal-backdrop" @click.self="closePromotionAdjust">
      <section class="promotion-adjust-modal panel" role="dialog" aria-modal="true" aria-labelledby="promotion-adjust-title">
        <div class="modal-header">
          <div><h2 id="promotion-adjust-title">📊 调整投产</h2><p>已选择 {{ selectedLinks.length }} 条链接，请确认调整范围</p></div>
          <button type="button" class="modal-close" aria-label="关闭弹窗" :disabled="adjustingPromotion" @click="closePromotionAdjust">×</button>
        </div>
        <div class="adjust-selection-list">
          <div v-for="item in selectedLinkRows" :key="item.linkId" class="adjust-selection-item"><code>{{ item.linkId }}</code><span>{{ item.storeName || '未识别店铺' }}</span></div>
        </div>
         <div class="adjust-form">
           <fieldset class="adjust-preset-fieldset"><legend>选择调整档次</legend><div class="adjust-preset-grid" role="radiogroup" aria-label="投产调整档次"><label v-for="preset in promotionAdjustPresets" :key="preset.key" class="adjust-preset" :class="{ 'is-selected': adjustPreset === preset.value }"><input v-model="adjustPreset" type="radio" name="promotion-adjust-preset" :value="preset.value" /><span class="adjust-preset-copy"><strong>{{ preset.label }}</strong><small>{{ preset.display }}</small></span></label></div></fieldset>
           <p class="adjust-preset-hint">提交后将按选中的档次上调投产比。</p>
         </div>
        <p v-if="adjustMessage" class="adjust-message">{{ adjustMessage }}</p>
        <div class="modal-actions"><button type="button" class="button secondary" :disabled="adjustingPromotion" @click="closePromotionAdjust">取消</button><button type="button" class="button primary" :disabled="adjustingPromotion" @click="submitPromotionAdjust">{{ adjustingPromotion ? '提交中…' : '确定提交' }}</button></div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, nextTick, onMounted, reactive, ref, watch } from 'vue';
import ChartPanel from './components/ChartPanel.vue';
import { useProfitData } from './composables/useProfitData';

const navItems = [
  { key: 'products', label: '商品分析', icon: '◇' },
  { key: 'analysis', label: '多维分析', icon: '⌗' },
  { key: 'links', label: '链接明细', icon: '⌁' },
  { key: 'product-management', label: '商品管理', icon: '▥' },
  { key: 'link-summary', label: '链接汇总', icon: '▤' },
  { key: 'cost', label: '成本结构', icon: '◒' },
  { key: 'admin', label: '管理中台', icon: '⚙' },
];

const colorTokens = Object.freeze({
  blue: '#3498db',
  blueDark: '#2980b9',
  teal: '#1abc9c',
  green: '#2ecc71',
  rose: '#e74c3c',
  amber: '#f39c12',
  purple: '#9b59b6',
  gray: '#7f8c8d',
  terracotta: '#e67e22',
  pink: '#e84393',
  slate: '#34495e',
});
const brandColors = Object.freeze({ 浪奇: colorTokens.blue, 白牌: colorTokens.gray, 威王: colorTokens.green, 舒蕾: colorTokens.purple });

const { data, status, targets, standards, loading, error, lastUpdated, links, linksMeta, linksLoading, linkFields: linkFieldsRef, linkDashboard, linkDashboardLoading, linkSummary, linkSummaryLoading, availableDates, loadAll, refresh, queryLinks, loadLinks, loadLinkDashboard, loadLinkSummary, saveTargets, saveStandard, deleteStandard, submitDelist, submitPromotionAdjust: sendPromotionAdjust } = useProfitData();
// 字段接口首次加载或热更新期间可能暂时没有返回 ref；当前数据库字段仍由 linkFieldOrder 提供完整兜底。
const linkFields = linkFieldsRef || ref([]);
const activeTab = ref('products');
const expandedGoalNodes = ref(new Set());
const sidebarCollapsed = ref(false);
const dateStart = ref('');
const dateEnd = ref('');
const rangePreset = ref('');
const datePresetOptions = Object.freeze([{ key: 'yesterday', label: '昨日' }, { key: '3d', label: '近 3 天' }, { key: '7d', label: '近 7 天' }, { key: '14d', label: '近 14 天' }, { key: '30d', label: '近 30 天' }]);
const creationPresetOptions = Object.freeze([{ key: 'yesterday', label: '昨日', days: 1 }, { key: '3d', label: '3天', days: 3 }, { key: '7d', label: '7天', days: 7 }, { key: '14d', label: '14天', days: 14 }, { key: '30d', label: '30天', days: 30 }]);
const creationFilter = reactive({ mode: 'age', days: 30, start: '', end: '' });
const activeMonth = ref('');
const analysisDimension = ref('brand');
const analysisMetric = ref('profitRate');
const standardRows = ref([]);
let standardFilterId = 0;
const showPersonLines = ref(false);
const focusedProfitRateSeries = ref(null);
const focusedProductProfitSeries = ref(null);
const targetForm = reactive({ monthTarget: 0, profitRate: 0, persons: {}, brands: {} });
const savingTargets = ref(false);
const targetMessage = ref('');
const selectedLinks = ref([]);
const adjustModalOpen = ref(false);
const adjustingPromotion = ref(false);
 const promotionAdjustPresets = Object.freeze([
   { key: 'maintenance-005', label: '日常维护', display: '+0.05', value: 0.05 },
   { key: 'serious-loss-01', label: '亏损严重', display: '+0.1', value: 0.1 },
   { key: 'serious-loss-02', label: '亏损严重', display: '+0.2', value: 0.2 },
   { key: 'maintenance-001', label: '日常维护', display: '+0.01', value: 0.01 },
 ]);
 const adjustPreset = ref(0.05);
const adjustMessage = ref('');
const linkQuery = reactive({ search: '', store_person: '', profit_rate_lte: '', size: 20 });
const linkSummaryQuery = reactive({ search: '', size: 20 });
const linkSummarySort = reactive({ key: 'revenue', order: 'desc' });
const expandedLinkSummaryId = ref('');
const linkSummaryDailyRows = ref([]);
const linkSummaryDailyLoading = ref(false);
const linkSummaryDailyError = ref('');
const brandOptions = Object.freeze(['浪奇', '威王', '舒蕾', '白牌']);
const globalFilters = reactive({ link_ids: '', product_code: '', product_name: '', brand: '', store_name: '', store_person: '' });
const linkDataDateStart = ref('');
const linkDataDateEnd = ref('');
const linkDataLinkIds = ref('');
const linkColumnsOpen = ref(false);
const visibleLinkColumnKeys = ref(null);
const linkFilters = reactive([]);
let linkFilterId = 0;
const linkDetailExpanded = ref(true);
const linkAlertOpen = reactive({ a15: true, a10: false, a5: false });
let linkRefreshTimer = null;

const currentNav = computed(() => navItems.find((item) => item.key === activeTab.value) || navItems[0]);
const hasData = computed(() => (data.value.dailyOverall || []).length > 0);
const statusText = computed(() => status.value?.database ? `${status.value.database.rows?.toLocaleString?.() || 0} 行数据` : '等待状态');
const peopleNames = computed(() => (data.value.peopleSummary || []).map((item) => item.name).filter(Boolean));
const brandNames = computed(() => {
  const names = new Set(Object.keys(targets.value[activeMonth.value]?.brands || {}));
  (data.value.allStores || []).forEach((item) => names.add(brandOf(item.store)));
  return [...names].filter(Boolean);
});
const targetMonths = computed(() => {
  const months = new Set(Object.keys(targets.value || {}));
  if (availableDates.value.length) months.add(availableDates.value.at(-1).slice(0, 7));
  return [...months].sort();
});
const activeTarget = computed(() => targets.value[activeMonth.value] || {});
const filteredDays = computed(() => (data.value.dailyOverall || []).filter((item) => {
  const day = String(item.date).slice(0, 10);
  return (!dateStart.value || day >= dateStart.value) && (!dateEnd.value || day <= dateEnd.value);
}));
const rangeHint = computed(() => filteredDays.value.length ? `${dateStart.value} 至 ${dateEnd.value} · ${filteredDays.value.length} 天` : '等待 API 返回日期');
const creationFilterHint = computed(() => creationFilter.mode === 'age' ? `链接创建：近 ${Math.max(1, Number(creationFilter.days || 1))} 天（截至昨日）` : `链接创建：${creationFilter.start || '起始'} 至 ${creationFilter.end || '结束'}`);
const derivedGrand = computed(() => {
  const total = filteredDays.value.reduce((acc, item) => {
    ['revenue', 'cost', 'shipping', 'promotion', 'profit', 'orders'].forEach((key) => { acc[key] += Number(item[key] || 0); });
    return acc;
  }, { revenue: 0, cost: 0, shipping: 0, promotion: 0, profit: 0, orders: 0 });
  total.grossProfit = total.revenue - total.cost - total.shipping;
  total.grossMargin = ratio(total.grossProfit, total.revenue);
  total.profitRate = ratio(total.profit, total.revenue);
  return total;
});

const peopleRows = computed(() => (data.value.peopleSummary || []).map((base) => {
  const current = filteredDays.value.reduce((acc, day) => {
    const row = data.value.dailyByPerson?.[String(day.date).slice(0, 10)]?.[base.name];
    if (row) ['revenue', 'cost', 'shipping', 'promotion', 'profit', 'orders'].forEach((key) => { acc[key] += Number(row[key] || 0); });
    return acc;
  }, { revenue: 0, cost: 0, shipping: 0, promotion: 0, profit: 0, orders: 0 });
  const fallback = filteredDays.value.length === (data.value.dailyOverall || []).length;
  const source = fallback && current.revenue === 0 ? base : current;
  return { ...base, ...source, grossProfit: source.revenue - source.cost - source.shipping, grossMargin: ratio(source.revenue - source.cost - source.shipping, source.revenue), promotionPct: ratio(source.promotion, source.revenue), profitRate: ratio(source.profit, source.revenue) };
}).filter((row) => row.name));

const personOverviewRows = computed(() => {
  const rows = peopleRows.value;
  if (!rows.length) return [];
  const total = rows.reduce((acc, row) => {
    ['stores', 'orders', 'revenue', 'cost', 'shipping', 'promotion', 'profit'].forEach((key) => { acc[key] += Number(row[key] || 0); });
    return acc;
  }, { stores: 0, orders: 0, revenue: 0, cost: 0, shipping: 0, promotion: 0, profit: 0 });
  const grossProfit = total.revenue - total.cost - total.shipping;
  return [...rows, { name: '📊 合计', ...total, grossProfit, grossMargin: ratio(grossProfit, total.revenue), promotionPct: ratio(total.promotion, total.revenue), profitRate: ratio(total.profit, total.revenue), total: true }];
});

const overviewInsights = computed(() => {
  const rows = peopleRows.value.filter((row) => row.revenue > 0);
  if (!rows.length) return [];
  const topRevenue = [...rows].sort((a, b) => b.revenue - a.revenue)[0];
  const bestMargin = [...rows].sort((a, b) => b.grossMargin - a.grossMargin)[0];
  const lowestProfit = [...rows].sort((a, b) => a.profitRate - b.profitRate)[0];
  return [
    { key: 'top-revenue', icon: '🏆', label: `${topRevenue.name}营收最高`, value: formatWan(topRevenue.revenue), suffix: `（${Number(topRevenue.stores || 0).toLocaleString()}店）`, tone: 'blue' },
    { key: 'best-margin', icon: '📈', label: `${bestMargin.name}毛利率最高`, value: `${bestMargin.grossMargin.toFixed(1)}%`, suffix: `但利润率仅 ${bestMargin.profitRate.toFixed(1)}%（推广影响利润）`, tone: 'teal' },
    { key: 'lowest-profit', icon: '⚠️', label: `${lowestProfit.name}利润率最低`, value: `${lowestProfit.profitRate.toFixed(1)}%`, suffix: `，推广占比 ${lowestProfit.promotionPct.toFixed(1)}%`, tone: 'danger' },
    { key: 'overall-profit', icon: '📊', label: '整体利润率', value: `${derivedGrand.value.profitRate.toFixed(1)}%`, suffix: `，推广费占收入 ${ratio(derivedGrand.value.promotion, derivedGrand.value.revenue).toFixed(1)}%`, tone: 'danger' },
  ];
});

const overviewAdvice = computed(() => {
  const rows = peopleRows.value.filter((row) => row.revenue > 0);
  const total = derivedGrand.value;
  const overallPromotionPct = ratio(total.promotion, total.revenue);
  const maxPromotion = rows.reduce((best, row) => row.promotionPct > best.promotionPct ? row : best, rows[0] || { name: '—', promotionPct: 0 });
  const lowestProfit = rows.reduce((best, row) => row.profitRate < best.profitRate ? row : best, rows[0] || { name: '—', profitRate: 0 });
  const topRevenue = rows.reduce((best, row) => row.revenue > best.revenue ? row : best, rows[0] || { name: '—', revenue: 0 });
  const costShippingPct = ratio(total.cost + total.shipping, total.revenue);
  return [
    { key: 'promotion', icon: '🔴', title: '推广费控制', color: colorTokens.rose, bar: Math.min(overallPromotionPct / 40 * 100, 100), description: `整体推广费占比 ${overallPromotionPct.toFixed(1)}%，${maxPromotion.name}推广占比最高达 ${maxPromotion.promotionPct.toFixed(1)}%。建议设推广费上限为收入的 25%，亏损店铺立即停投。` },
    { key: 'profit', icon: '🟠', title: '利润率优化', color: colorTokens.amber, bar: Math.max(100 - total.profitRate / 15 * 100, 20), description: `整体利润率仅 ${total.profitRate.toFixed(1)}%，${lowestProfit.name}最低 ${lowestProfit.profitRate.toFixed(1)}%。建议优先优化低利润率负责人的商品结构，砍掉持续亏损 SKU。` },
    { key: 'revenue', icon: '🟢', title: '营收增长', color: colorTokens.green, bar: 70, description: `${topRevenue.name}营收最高 ${formatWan(topRevenue.revenue)}，但需关注推广效率。建议对高营收低利润负责人做专项分析，提升每元推广回报率。` },
    { key: 'cost', icon: '🔵', title: '成本结构', color: colorTokens.blue, bar: Math.min(costShippingPct, 100), description: `货品成本+快递费合计占收入 ${costShippingPct.toFixed(1)}%，重点关注推广费（${overallPromotionPct.toFixed(1)}%）和退货率的改善空间。` },
    { key: 'risk', icon: '⚠️', title: '风险预警', color: colorTokens.purple, bar: 85, description: '利润率低于 3% 的负责人需重点关注；推广费占比超过 35% 的负责人存在推广过度风险，建议按周监控并设置预警线。' },
  ];
});

const storeRows = computed(() => {
  const totals = new Map();
  filteredDays.value.forEach((day) => {
    const dayStores = data.value.dailyByStore?.[String(day.date).slice(0, 10)] || {};
    Object.entries(dayStores).forEach(([store, value]) => {
      const current = totals.get(store) || { orders: 0, revenue: 0, cost: 0, shipping: 0, promotion: 0, platformProfit: 0 };
      ['orders', 'revenue', 'cost', 'shipping', 'promotion'].forEach((key) => { current[key] += Number(value?.[key] || 0); });
      current.platformProfit += Number(value?.profit || 0);
      totals.set(store, current);
    });
  });
  const baseStores = data.value.allStores || [];
  const baseByStore = new Map(baseStores.map((row) => [row.store, row]));
  const storeNames = new Set([...baseByStore.keys(), ...totals.keys()]);
  return [...storeNames].map((store) => {
    const base = baseByStore.get(store) || {};
    const total = totals.get(store) || { orders: 0, revenue: 0, cost: 0, shipping: 0, promotion: 0, platformProfit: 0 };
    const revenue = Number(total.revenue || 0);
    const cost = Number(total.cost || 0);
    const shipping = Number(total.shipping || 0);
    const promotion = Number(total.promotion || 0);
    const platformProfit = Number(total.platformProfit || 0);
    const grossProfit = revenue - cost - shipping;
    return {
      person: base.person || '—',
      store,
      orders: Number(total.orders || 0),
      revenue,
      cost,
      costPct: ratio(cost, revenue),
      shipping,
      shippingPct: ratio(shipping, revenue),
      grossProfit,
      grossMargin: ratio(grossProfit, revenue),
      promotion,
      promotionPct: ratio(promotion, revenue),
      platformProfit,
      profitRate: ratio(platformProfit, revenue),
    };
  }).sort((a, b) => b.revenue - a.revenue);
});

const storeInsights = computed(() => {
  const rows = storeRows.value.filter((row) => row.revenue > 0);
  if (!rows.length) return [];
  const topStore = rows[0];
  const bestProfit = [...rows].sort((a, b) => b.profitRate - a.profitRate)[0];
  const lossCount = rows.filter((row) => row.profitRate < 0).length;
  const highPromoCount = rows.filter((row) => row.promotionPct > 50).length;
  return [
    { key: 'top-revenue', icon: '🏆', label: '最高营收', value: topStore.store, suffix: `（${topStore.person}）${formatMoney(topStore.revenue)} 元`, tone: 'blue' },
    { key: 'best-profit', icon: '📈', label: '最高利润率', value: `${bestProfit.store} ${bestProfit.profitRate.toFixed(1)}%`, suffix: `（${bestProfit.orders.toLocaleString()} 单）`, tone: 'teal' },
    { key: 'risk', icon: '⚠️', label: `${lossCount} 家店铺亏损`, value: `${highPromoCount} 家推广占比过半`, suffix: '', tone: 'danger' },
  ];
});

const storeQuadrantRows = computed(() => storeRows.value.filter((row) => row.revenue > 50));
const storeLossRows = computed(() => storeRows.value.filter((row) => row.profitRate < 0).sort((a, b) => a.profitRate - b.profitRate).slice(0, 10));

const productRows = computed(() => {
  const merged = new Map();
  (data.value.products || []).forEach((row) => {
    const code = String(row.code || '').split('-')[0];
    if (!code) return;
    const current = merged.get(code) || { code, name: row.name || '—', revenue: 0, cost: 0, shipping: 0, promotion: 0, platformProfit: 0, orders: 0 };
    current.name = current.name === '—' ? (row.name || '—') : current.name;
    current.revenue += Number(row.revenue || 0);
    current.cost += Number(row.cost || 0);
    current.shipping += Number(row.shipping || 0);
    current.promotion += Number(row.promotion || 0);
    current.platformProfit += Number(row.platform_profit ?? row.platformProfit ?? 0);
    current.orders += Number(row.orders || 0);
    merged.set(code, current);
  });

  const actuals = new Map();
  filteredDays.value.forEach((day) => {
    const dayProducts = data.value.dailyByProduct?.[String(day.date).slice(0, 10)] || {};
    Object.entries(dayProducts).forEach(([code, value]) => {
      const baseCode = String(code).split('-')[0];
      const current = actuals.get(baseCode) || { revenue: 0, platformProfit: 0 };
      current.revenue += Number(value?.revenue || 0);
      current.platformProfit += Number(value?.profit || 0);
      actuals.set(baseCode, current);
    });
  });

  return [...merged.entries()].map(([code, base]) => {
    const actual = actuals.get(code) || { revenue: 0, platformProfit: 0 };
    const scale = base.revenue > 0 ? actual.revenue / base.revenue : 0;
    const cost = base.cost * scale;
    const shipping = base.shipping * scale;
    const promotion = base.promotion * scale;
    const grossProfit = actual.revenue - cost - shipping;
    return {
      code,
      name: base.name,
      orders: Math.round(base.orders * scale),
      revenue: actual.revenue,
      cost,
      costPct: ratio(cost, actual.revenue),
      shipping,
      shippingPct: ratio(shipping, actual.revenue),
      grossProfit,
      grossMargin: ratio(grossProfit, actual.revenue),
      promotion,
      promotionPct: ratio(promotion, actual.revenue),
      platformProfit: actual.platformProfit,
      profitRate: ratio(actual.platformProfit, actual.revenue),
    };
  }).sort((a, b) => b.revenue - a.revenue);
});

const productInsights = computed(() => {
  const rows = productRows.value.filter((row) => row.revenue > 0);
  if (!rows.length) return [];
  const top = rows[0];
  const highProfit = rows.filter((row) => row.profitRate > 10).length;
  const loss = rows.filter((row) => row.profitRate < 0).length;
  return [
    { key: 'top', icon: '📦', label: `${rows.length} 个商品编码 · TOP1`, value: top.code, suffix: `收入 ${formatWan(top.revenue)}（占比 ${ratio(top.revenue, derivedGrand.value.revenue).toFixed(0)}%）`, tone: 'blue' },
    { key: 'health', icon: '✅', label: `${highProfit} 个商品利润率 >10% · ⚠️`, value: `${loss} 个亏损`, suffix: '', tone: 'danger' },
    { key: 'structure', icon: '🔑', label: '品类结构', value: '洗衣液/清洁剂', suffix: '毛利率较高但推广占比偏高', tone: 'teal' },
  ];
});

const productAdvice = computed(() => {
  const rows = productRows.value.filter((row) => row.revenue > 0);
  if (!rows.length) return [];
  const positive = rows.filter((row) => row.revenue > 100 && row.profitRate > 0);
  const topRevenue = positive[0] || rows[0];
  const bestProfit = [...positive].sort((a, b) => b.profitRate - a.profitRate)[0] || rows[0];
  const smallLoss = rows.filter((row) => row.revenue < 100 && row.profitRate < 0).sort((a, b) => a.profitRate - b.profitRate);
  const highPromo = rows.filter((row) => row.promotionPct > 40).length;
  const totalRevenue = rows.reduce((sum, row) => sum + row.revenue, 0);
  return [
    { key: 'loss', icon: '🔴', title: '亏损预警', color: colorTokens.rose, description: `${smallLoss.length} 个小量商品亏损。${smallLoss[0] ? `亏损最严重：[${smallLoss[0].code}] ${smallLoss[0].profitRate.toFixed(1)}%` : '当前暂无小量亏损商品'}。建议立即停投持续亏损 SKU，每周审查。` },
    { key: 'promotion', icon: '🟠', title: '推广过度', color: colorTokens.amber, description: `${highPromo} 个商品推广占比 >40%。建议缩减高推广占比商品投放，按周设置 ROI 预警线。` },
    { key: 'best', icon: '🟢', title: '爆款识别', color: colorTokens.green, description: `[${topRevenue.code}] 收入最高 ${formatWan(topRevenue.revenue)}。利润率最高：[${bestProfit.code}] ${bestProfit.profitRate.toFixed(1)}%。建议加大优质商品投放。` },
    { key: 'structure', icon: '🔵', title: '品类结构', color: colorTokens.blue, description: `共 ${rows.length} 个有效商品编码，筛选期总收入 ${formatWan(totalRevenue)}。洗衣液/清洁剂类毛利率高但推广吃利，建议控制推广预算。` },
  ];
});

const productProfitRangeRows = computed(() => {
  const daily = new Map();
  filteredDays.value.forEach((day) => {
    const date = String(day.date).slice(0, 10);
    const dayProducts = data.value.dailyByProduct?.[date] || {};
    Object.entries(dayProducts).forEach(([code, value]) => {
      const baseCode = String(code).split('-')[0];
      const row = daily.get(baseCode) || { revenue: 0, profit: 0, daily: {} };
      const revenue = Number(value?.revenue || 0);
      const profit = Number(value?.profit || 0);
      row.revenue += revenue;
      row.profit += profit;
      row.daily[date] = row.daily[date] || { revenue: 0, profit: 0 };
      row.daily[date].revenue += revenue;
      row.daily[date].profit += profit;
      daily.set(baseCode, row);
    });
  });
  const nameByCode = new Map(productRows.value.map((row) => [row.code, row.name]));
  return [...daily.entries()].map(([code, row]) => ({ code, name: nameByCode.get(code) || code, ...row })).sort((a, b) => b.revenue - a.revenue).slice(0, 10);
});

const goalRows = computed(() => peopleRows.value.map((row) => {
  const target = Number(activeTarget.value.persons?.[row.name] || 0);
  return { name: row.name, actual: row.revenue / 10000, target, rate: target ? row.revenue / 10000 / target * 100 : 0 };
}));
const brandRows = computed(() => brandNames.value.map((brand) => {
  const actual = storeRows.value.filter((row) => brandOf(row.store) === brand).reduce((sum, row) => sum + row.revenue, 0) / 10000;
  const target = Number(activeTarget.value.brands?.[brand] || 0);
  return { name: brand, actual, target, rate: target ? actual / target * 100 : 0 };
}));

const analysisDimensionLabel = computed(() => ({ brand: '品牌', product: '商品', store: '店铺', person: '负责人' }[analysisDimension.value] || '维度'));
const analysisMetricLabel = computed(() => ({ profitRate: '利润率', grossMargin: '毛利率', promotionPct: '推广占比', revenue: '收入', orders: '单量' }[analysisMetric.value] || '指标'));
const analysisBaseRows = computed(() => {
  if (analysisDimension.value === 'brand') {
    const grouped = new Map();
    storeRows.value.forEach((row) => {
      const name = brandOf(row.store);
      const current = grouped.get(name) || { name, revenue: 0, orders: 0, cost: 0, shipping: 0, promotion: 0, platformProfit: 0 };
      ['revenue', 'orders', 'cost', 'shipping', 'promotion', 'platformProfit'].forEach((key) => { current[key] += Number(row[key] || 0); });
      grouped.set(name, current);
    });
    return [...grouped.values()].map((row) => ({ ...row, grossProfit: row.revenue - row.cost - row.shipping, grossMargin: ratio(row.revenue - row.cost - row.shipping, row.revenue), promotionPct: ratio(row.promotion, row.revenue), profitRate: ratio(row.platformProfit, row.revenue) }));
  }
  if (analysisDimension.value === 'product') return productRows.value.map((row) => ({ ...row, name: row.code, detail: row.name }));
  if (analysisDimension.value === 'store') return storeRows.value.map((row) => ({ ...row, name: row.store, detail: row.person }));
  return peopleRows.value.map((row) => ({ ...row, name: row.name, detail: `${Number(row.stores || 0).toLocaleString()} 店` }));
});
const analysisRows = computed(() => analysisBaseRows.value.map((row) => {
  const standard = (standards.value || []).find((item) => {
    if (!item.enabled || item.metricKey !== analysisMetric.value || item.dimensionType !== analysisDimension.value) return false;
    if (item.brand && item.brand !== (analysisDimension.value === 'brand' ? row.name : brandOf(row.store || ''))) return false;
    if (item.productCode && !String(row.code || '').toLowerCase().includes(String(item.productCode).toLowerCase())) return false;
    if (item.productName && !String(row.detail || row.name || '').toLowerCase().includes(String(item.productName).toLowerCase())) return false;
    return true;
  });
  const value = Number(row[analysisMetric.value] || 0);
  let status = '未配置';
  if (standard) {
    const min = Number(standard.thresholdMin);
    const max = Number(standard.thresholdMax);
    const pass = standard.operator === 'between' ? ((!Number.isFinite(min) || value >= min) && (!Number.isFinite(max) || value <= max)) : standard.operator === 'lte' ? (!Number.isFinite(min) || value <= min) : (!Number.isFinite(min) || value >= min);
    status = pass ? '达标' : '不达标';
  }
  return { ...row, dimension: analysisDimensionLabel.value, metricValue: value, standard: standard ? `${standard.operator === 'between' ? `${standard.thresholdMin ?? '—'} ~ ${standard.thresholdMax ?? '—'}` : `${standard.operator === 'lte' ? '≤' : '≥'} ${standard.thresholdMin ?? '—'}`}` : '未配置', status, statusTone: status === '达标' ? 'rate' : status === '不达标' ? 'negative' : 'warning' };
}).sort((a, b) => b.metricValue - a.metricValue));
const analysisStatusCounts = computed(() => analysisRows.value.reduce((counts, row) => { if (row.status === '达标') counts.pass += 1; else if (row.status === '不达标') counts.fail += 1; else counts.watch += 1; return counts; }, { pass: 0, watch: 0, fail: 0 }));
const analysisColumns = computed(() => [
  { key: 'name', label: analysisDimensionLabel.value },
  { key: 'detail', label: analysisDimension.value === 'product' ? '商品名称' : analysisDimension.value === 'store' ? '负责人' : '辅助信息' },
  { key: 'revenue', label: '收入', format: formatWan },
  { key: 'orders', label: '单量', format: (v) => Number(v || 0).toLocaleString() },
  { key: 'metricValue', label: analysisMetricLabel.value, format: (v) => ['revenue'].includes(analysisMetric.value) ? formatWan(v) : analysisMetric.value === 'orders' ? Number(v || 0).toLocaleString() : `${Number(v || 0).toFixed(1)}%`, tone: analysisMetric.value === 'revenue' ? '' : 'rate' },
  { key: 'standard', label: '后台标准' },
  { key: 'status', label: '状态', tone: 'statusTone' },
]);

const targetTree = computed(() => {
  const source = activeTarget.value || {};
  const brands = Object.entries(source.brands || {}).map(([name, value]) => ({ name, value: Number(value || 0) })).filter((item) => item.name && item.value > 0).sort((a, b) => b.value - a.value);
  const persons = Object.entries(source.persons || {}).map(([name, value]) => ({ name, value: Number(value || 0) })).filter((item) => item.name && item.value > 0).sort((a, b) => b.value - a.value);
  const brandTotal = brands.reduce((sum, item) => sum + item.value, 0);
  const personTotal = persons.reduce((sum, item) => sum + item.value, 0);
  const monthTarget = Number(source.monthTarget || 0) || Math.max(brandTotal, personTotal);
  return {
    monthTarget,
    brands,
    persons,
    brandTotal,
    personTotal,
    brandShare: monthTarget ? brandTotal / monthTarget * 100 : 0,
    personShare: monthTarget ? personTotal / monthTarget * 100 : 0,
  };
});

const personGoalRows = computed(() => {
  const baseRows = goalRows.value;
  const configuredTarget = baseRows.some((row) => row.target > 0);
  const fallbackTarget = !configuredTarget && targetTree.value.monthTarget > 0 && baseRows.length ? targetTree.value.monthTarget * 0.48 / baseRows.length : 0;
  const rows = baseRows.map((row) => {
    const target = configuredTarget ? row.target : fallbackTarget;
    const rate = target > 0 ? row.actual / target * 100 : 0;
    return { dimension: '负责人', name: row.name, target, actual: row.actual, rate, gap: target - row.actual, status: rate >= 100 ? '✅ 已达成' : rate >= 70 ? '🟡 进行中' : rate > 0 ? '🔴 落后' : '⚪ 未启动' };
  });
  const target = rows.reduce((sum, row) => sum + row.target, 0);
  const actual = rows.reduce((sum, row) => sum + row.actual, 0);
  return [...rows, { dimension: '📊 合计', name: `${rows.length}人`, target, actual, rate: target > 0 ? actual / target * 100 : 0, gap: target - actual, status: '—', total: true }];
});

const brandGoalRows = computed(() => {
  const baseRows = brandRows.value;
  if (!baseRows.length) return [];
  const configuredTarget = baseRows.some((row) => row.target > 0);
  const fallbackTarget = !configuredTarget && targetTree.value.monthTarget > 0 ? targetTree.value.monthTarget * 0.52 / baseRows.length : 0;
  const rows = baseRows.map((row) => {
    const target = configuredTarget ? row.target : fallbackTarget;
    const rate = target > 0 ? row.actual / target * 100 : 0;
    return { dimension: '品牌', name: row.name, target, actual: row.actual, rate, gap: target - row.actual, status: rate >= 100 ? '✅ 已达成' : rate >= 70 ? '🟡 进行中' : rate > 0 ? '🔴 落后' : '⚪ 未启动' };
  });
  const target = rows.reduce((sum, row) => sum + row.target, 0);
  const actual = rows.reduce((sum, row) => sum + row.actual, 0);
  return [...rows, { dimension: '📊 合计', name: `${rows.length}品牌`, target, actual, rate: target > 0 ? actual / target * 100 : 0, gap: target - actual, status: '—', total: true }];
});

const goalAlerts = computed(() => {
  const buildAlert = (row, type) => {
    if (!row.target || row.rate >= 90) return null;
    const severe = row.rate < 60;
    return {
      key: `${type}-${row.name}`,
      name: row.name,
      rate: row.rate,
      severity: severe ? 'danger' : 'warning',
      icon: severe ? '🔴' : '🟠',
      message: type === 'person' ? '负责人目标完成率仅' : '品牌完成率仅',
      suffix: severe ? (type === 'person' ? '，严重落后，需重点关注' : '，建议优化该品牌产品线和推广投入') : '，建议加强执行与复盘',
    };
  };
  const personAlerts = goalRows.value.map((row) => buildAlert(row, 'person')).filter(Boolean).sort((a, b) => a.rate - b.rate).slice(0, 3);
  const brandAlerts = brandRows.value.map((row) => buildAlert(row, 'brand')).filter(Boolean).sort((a, b) => a.rate - b.rate).slice(0, 3);
  const alerts = [...personAlerts, ...brandAlerts];
  return alerts.length ? alerts : [{ key: 'none', name: '当前范围', rate: null, severity: 'info', icon: '✅', message: '暂无需要预警的目标项', suffix: '所有已配置目标完成率均达到 90% 以上' }];
});

const goalKpiCards = computed(() => {
  const total = derivedGrand.value;
  const monthTarget = Number(activeTarget.value.monthTarget || 0);
  const targetProfitRate = Number(activeTarget.value.profitRate || 0);
  const gsvWan = total.revenue / 10000;
  const profitWan = total.profit / 10000;
  const actualProfitRate = ratio(total.profit, total.revenue);
  const gsvCompletionRate = monthTarget > 0 ? gsvWan / monthTarget * 100 : 0;
  const targetProfitWan = monthTarget * targetProfitRate / 100;
  const profitCompletionRate = targetProfitWan > 0 ? profitWan / targetProfitWan * 100 : 0;
  const profitRateDiff = actualProfitRate - targetProfitRate;
  const gapWan = monthTarget - gsvWan;
  const now = new Date();
  const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
  const remainingDays = Math.max(0, lastDay - now.getDate() + 1);
  const dailyNeededWan = remainingDays > 0 ? gapWan / remainingDays : 0;
  const storeCount = new Set(filteredDays.value.flatMap((day) => Object.keys(data.value.dailyByStore?.[String(day.date).slice(0, 10)] || {}))).size;
  const targetMonthParts = (activeMonth.value || `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`).split('-');
  const targetMonthLabel = `${targetMonthParts[0]}年${Number(targetMonthParts[1])}月`;
  const progressTone = gsvCompletionRate >= 90 ? 'positive' : gsvCompletionRate >= 60 ? 'warning' : 'negative';
  const profitCompletionTone = profitCompletionRate >= 90 ? 'positive' : profitCompletionRate >= 60 ? 'warning' : 'negative';
  const diffTone = profitRateDiff >= 0 ? 'positive' : 'negative';
  const gapTone = gapWan >= 0 ? 'negative' : 'positive';

  return [
    { label: '当月销售目标', value: monthTarget > 0 ? monthTarget.toFixed(0) : '--', unit: '万', subParts: [{ text: `${storeCount}店铺合计` }], icon: '◎' },
    { label: '实际销售 GSV', value: gsvWan.toFixed(1), unit: '万', subParts: [{ text: '完成率 ' }, { text: `${gsvCompletionRate.toFixed(1)}%`, tone: progressTone }], icon: '↗' },
    { label: '实际利润率', value: actualProfitRate.toFixed(1), unit: '%', subParts: [{ text: '目标利润率：' }, { text: `${targetProfitRate.toFixed(1)}%` }, { text: ' · 差值：' }, { text: `${profitRateDiff >= 0 ? '+' : ''}${profitRateDiff.toFixed(1)}%`, tone: diffTone }], icon: '✓' },
    { label: '利润值', value: profitWan.toFixed(1), unit: '万', valueTone: profitWan >= 0 ? 'positive' : 'negative', subParts: [{ text: '完成率：' }, { text: `${profitCompletionRate.toFixed(1)}%`, tone: profitCompletionTone }], icon: '◔' },
    { label: '每日需完成', value: dailyNeededWan.toFixed(1), unit: '万', valueTone: dailyNeededWan >= 0 ? 'negative' : 'positive', subParts: [{ text: '剩余' }, { text: `${remainingDays}`, tone: 'emphasis' }, { text: '天 · 差距' }, { text: `${gapWan.toFixed(1)}`, tone: gapTone }, { text: '万' }], icon: '→' },
    { label: '📅 当月天数倒计时', value: `${remainingDays}`, unit: '天', valueTone: 'negative', subParts: [{ text: `${targetMonthLabel} · 剩余${remainingDays}天` }], icon: '⏰', cardClass: 'countdown-card' },
  ];
});

const kpiCards = computed(() => [
  { label: '营业收入', value: formatWan(derivedGrand.value.revenue), sub: `${derivedGrand.value.orders.toLocaleString()} 单 · ${filteredDays.value.length} 天`, icon: '↗' },
  { label: '毛利', value: formatWan(derivedGrand.value.grossProfit), sub: `毛利率 ${derivedGrand.value.grossMargin.toFixed(1)}%`, icon: '◔', tone: 'positive' },
  { label: '推广费', value: formatWan(derivedGrand.value.promotion), sub: `推广占比 ${ratio(derivedGrand.value.promotion, derivedGrand.value.revenue).toFixed(1)}%`, icon: '↯', tone: 'warning' },
  { label: '平台利润', value: formatWan(derivedGrand.value.profit), sub: `利润率 ${derivedGrand.value.profitRate.toFixed(1)}%`, icon: '✓', tone: derivedGrand.value.profit >= 0 ? 'positive' : 'negative' },
  { label: '货品成本', value: formatWan(derivedGrand.value.cost), sub: `成本占比 ${ratio(derivedGrand.value.cost, derivedGrand.value.revenue).toFixed(1)}%`, icon: '◫' },
  { label: '快递费', value: formatWan(derivedGrand.value.shipping), sub: `快递占比 ${ratio(derivedGrand.value.shipping, derivedGrand.value.revenue).toFixed(1)}%`, icon: '→' },
]);

const personColumns = [
  { key: 'name', label: '负责人' }, { key: 'revenue', label: '收入', format: (v) => formatWan(v) }, { key: 'orders', label: '单量', format: (v) => Number(v || 0).toLocaleString() }, { key: 'grossMargin', label: '毛利率', format: (v) => `${Number(v || 0).toFixed(1)}%` }, { key: 'promotionPct', label: '推广占比', format: (v) => `${Number(v || 0).toFixed(1)}%` }, { key: 'profitRate', label: '利润率', format: (v) => `${Number(v || 0).toFixed(1)}%`, tone: 'rate' },
];
const personOverviewColumns = [
  { key: 'name', label: '负责人' },
  { key: 'stores', label: '店铺数', format: (v) => Number(v || 0).toLocaleString() },
  { key: 'orders', label: '单量', format: (v) => Number(v || 0).toLocaleString() },
  { key: 'revenue', label: '收入(元)', format: (v) => Number(v || 0).toLocaleString() },
  { key: 'cost', label: '成本(元)', format: (v) => Number(v || 0).toLocaleString() },
  { key: 'shipping', label: '快递(元)', format: (v) => Number(v || 0).toLocaleString() },
  { key: 'grossProfit', label: '毛利(元)', format: (v) => Number(v || 0).toLocaleString() },
  { key: 'grossMargin', label: '毛利率', format: (v) => `${Number(v || 0).toFixed(1)}%` },
  { key: 'promotion', label: '推广费(元)', format: (v) => Number(v || 0).toLocaleString() },
  { key: 'promotionPct', label: '推广占比', format: (v) => `${Number(v || 0).toFixed(1)}%` },
  { key: 'profit', label: '平台利润(元)', format: (v) => Number(v || 0).toLocaleString() },
  { key: 'profitRate', label: '利润率', format: (v) => `${Number(v || 0).toFixed(1)}%`, tone: 'rate' },
];
const personGoalColumns = [
  { key: 'dimension', label: '维度' },
  { key: 'name', label: '名称' },
  { key: 'target', label: '目标(万)', format: (v) => Number(v || 0).toFixed(1) },
  { key: 'actual', label: '实际(万)', format: (v) => Number(v || 0).toFixed(1) },
  { key: 'rate', label: '完成率', format: (v) => `${Number(v || 0).toFixed(1)}%`, tone: 'rate' },
  { key: 'gap', label: '差距(万)', format: (v) => `${Number(v || 0) >= 0 ? '+' : ''}${Number(v || 0).toFixed(1)}` },
  { key: 'status', label: '状态' },
];
const brandGoalColumns = [
  { key: 'dimension', label: '维度' },
  { key: 'name', label: '名称' },
  { key: 'target', label: '目标(万)', format: (v) => Number(v || 0).toFixed(1) },
  { key: 'actual', label: '实际(万)', format: (v) => Number(v || 0).toFixed(1) },
  { key: 'rate', label: '完成率', format: (v) => `${Number(v || 0).toFixed(1)}%`, tone: 'rate' },
  { key: 'gap', label: '差距(万)', format: (v) => `${Number(v || 0) >= 0 ? '+' : ''}${Number(v || 0).toFixed(1)}` },
  { key: 'status', label: '状态' },
];
const storeColumns = [
  { key: 'person', label: '负责人' },
  { key: 'store', label: '店铺名称' },
  { key: 'orders', label: '单量', format: (v) => Number(v || 0).toLocaleString() },
  { key: 'revenue', label: '收入(元)', format: (v) => Number(v || 0).toLocaleString() },
  { key: 'costPct', label: '成本占比', format: (v) => `${Number(v || 0).toFixed(1)}%` },
  { key: 'shippingPct', label: '快递占比', format: (v) => `${Number(v || 0).toFixed(1)}%` },
  { key: 'grossMargin', label: '毛利率', format: (v) => `${Number(v || 0).toFixed(1)}%` },
  { key: 'promotion', label: '推广费(元)', format: (v) => Number(v || 0).toLocaleString() },
  { key: 'promotionPct', label: '推广占比', format: (v) => `${Number(v || 0).toFixed(1)}%` },
  { key: 'platformProfit', label: '平台利润(元)', format: (v) => Number(v || 0).toLocaleString(), tone: 'number' },
  { key: 'profitRate', label: '利润率', format: (v) => `${Number(v || 0).toFixed(1)}%`, tone: 'rate' },
];
const productColumns = [
  { key: 'code', label: '商品编码' },
  { key: 'name', label: '商品名称' },
  { key: 'orders', label: '单量', format: (v) => Number(v || 0).toLocaleString() },
  { key: 'revenue', label: '收入(元)', format: (v) => Number(v || 0).toLocaleString() },
  { key: 'costPct', label: '成本占比', format: (v) => `${Number(v || 0).toFixed(2)}%` },
  { key: 'shippingPct', label: '快递占比', format: (v) => `${Number(v || 0).toFixed(2)}%` },
  { key: 'grossMargin', label: '毛利率', format: (v) => `${Number(v || 0).toFixed(2)}%` },
  { key: 'promotion', label: '推广费(元)', format: (v) => Number(v || 0).toLocaleString() },
  { key: 'promotionPct', label: '推广占比', format: (v) => `${Number(v || 0).toFixed(2)}%` },
  { key: 'profitRate', label: '利润率', format: (v) => `${Number(v || 0).toFixed(2)}%`, tone: 'rate' },
];
const linkFieldOrder = [
  '链接id', '链接创建时间', '商品编码', '商品标题', '店铺名称', '品牌', '负责人', '数据日期', '单量', '收入', '成本', '成本占比', '快递', '快递占比', '成本+快递', '货品快递总和占比', '毛利', '毛利率', '技术服务费', '预估售后', '推广费', '推广费占比', '平台利润', '利润率', '运费险', '税费', '来源文件',
  '出价方式', '商品名称', 'store', '推广来源文件', '总花费(元)', '交易额(元)', '净交易额(元)', '净成交笔数', '成交笔数', '直接交易额(元)', '间接交易额(元)', '直接成交笔数', '间接成交笔数', '曝光量', '点击量', '询单花费(元)', '询单量', '收藏花费(元)', '收藏量', '关注花费(元)', '关注量', '平均收藏成本(元)', '平均关注成本(元)', '平均询单成本(元)', '全站推广费比', '净交易额占比', '实际投产比', '净实际投产比', '每笔净成交花费(元)', '每笔成交花费(元)', '每笔成交金额(元)', '每笔直接成交金额(元)', '每笔间接成交金额(元)', '推广数据匹配',
];
const linkPercentFields = new Set(['成本占比', '快递占比', '货品快递总和占比', '毛利率', '推广费占比', '利润率', '全站推广费比', '净交易额占比']);
const linkFieldLabels = Object.freeze({ 链接id: '链接 ID', 链接创建时间: '链接创建时间', 店铺名称: '店铺', 数据日期: '日期', 推广费占比: '推广占比', 推广数据匹配: '推广数据匹配' });
const linkColumnOptions = computed(() => {
  const apiFields = linkFields.value || [];
  const apiMap = new Map(apiFields.map((field) => [field.key, field]));
  const keys = apiFields.length ? linkFieldOrder.filter((key) => key === '品牌' || apiMap.has(key)) : linkFieldOrder;
  const extras = apiFields.map((field) => field.key).filter((key) => key !== 'id' && !keys.includes(key));
  return [...keys, ...extras].map((key) => {
    const apiField = apiMap.get(key);
    return { key, label: linkFieldLabels[key] || apiField?.label || key, type: key === '品牌' ? 'text' : (apiField?.type || (linkPercentFields.has(key) ? 'number' : 'text')) };
  });
});
const linkFilterFields = computed(() => linkColumnOptions.value);
const linkColumns = computed(() => {
  const selected = visibleLinkColumnKeys.value === null ? linkColumnOptions.value : linkColumnOptions.value.filter((column) => visibleLinkColumnKeys.value.includes(column.key));
  return selected.map((column) => ({ ...column, tone: linkPercentFields.has(column.key) ? 'rate' : column.type === 'number' ? 'number' : '' }));
});
const linkDashboardFixedColumns = [{ key: 'linkId', label: '链接ID' }, { key: 'productCode', label: '商品编码' }, { key: 'title', label: '商品标题' }, { key: 'storeName', label: '店铺名称' }, { key: 'brand', label: '品牌' }];

const linkDashboardRows = computed(() => linkDashboard.value.data || []);
const linkDashboardDates = computed(() => linkDashboard.value.dates || []);
const linkDashboardMeta = computed(() => ({
  total: linkDashboard.value.total || 0,
  page: linkDashboard.value.page || 1,
  pages: linkDashboard.value.pages || 0,
  size: linkDashboard.value.size || linkQuery.size,
}));
const linkSummaryRows = computed(() => linkSummary.value.data || []);
const linkSummaryMeta = computed(() => ({
  total: linkSummary.value.total || 0,
  page: linkSummary.value.page || 1,
  pages: linkSummary.value.pages || 0,
  size: linkSummary.value.size || linkSummaryQuery.size,
}));
const linkSummaryTotals = computed(() => ({
  links: 0,
  rows: 0,
  dataDays: 0,
  firstDate: '',
  lastDate: '',
  orders: 0,
  revenue: 0,
  cost: 0,
  costPct: 0,
  shipping: 0,
  shippingPct: 0,
  grossProfit: 0,
  grossMargin: 0,
  promotion: 0,
  promotionPct: 0,
  platformProfit: 0,
  profitRate: 0,
  ...linkSummary.value.summary,
}));
const linkSummaryTopRows = computed(() => linkSummaryRows.value.slice(0, 15));
const linkSummaryColumns = [
  { key: 'linkId', label: '链接 ID' },
  { key: 'productCode', label: '商品编码' },
  { key: 'title', label: '商品标题' },
  { key: 'storeName', label: '店铺' },
  { key: 'brand', label: '品牌' },
  { key: 'person', label: '负责人' },
  { key: 'dataDays', label: '天数', format: (v) => Number(v || 0).toLocaleString() },
  { key: 'orders', label: '单量', format: (v) => Number(v || 0).toLocaleString() },
  { key: 'revenue', label: '收入(万)', format: formatSummaryWan },
  { key: 'cost', label: '成本(万)', format: formatSummaryWan },
  { key: 'costPct', label: '成本占比', format: formatSummaryPercent, tone: 'rate' },
  { key: 'shipping', label: '快递(万)', format: formatSummaryWan },
  { key: 'shippingPct', label: '快递占比', format: formatSummaryPercent, tone: 'rate' },
  { key: 'costShipping', label: '成本+快递(万)', format: formatSummaryWan },
  { key: 'costShippingPct', label: '成本+快递占比', format: formatSummaryPercent, tone: 'rate' },
  { key: 'grossProfit', label: '毛利(万)', format: formatSummaryWan },
  { key: 'grossMargin', label: '毛利率', format: formatSummaryPercent, tone: 'rate' },
  { key: 'promotion', label: '推广费(万)', format: formatSummaryWan },
  { key: 'promotionPct', label: '推广占比', format: formatSummaryPercent, tone: 'rate' },
  { key: 'platformProfit', label: '平台利润(万)', format: formatSummaryWan },
  { key: 'profitRate', label: '利润率', format: formatSummaryPercent, tone: 'rate' },
  { key: 'firstDate', label: '开始日期' },
  { key: 'lastDate', label: '结束日期' },
];
const linkSummaryDailyColumns = [
  { key: '数据日期', label: '数据日期' },
  { key: '商品编码', label: '商品编码' },
  { key: '单量', label: '单量', tone: 'number' },
  { key: '收入', label: '收入', tone: 'number' },
  { key: '成本', label: '成本', tone: 'number' },
  { key: '成本占比', label: '成本占比', tone: 'rate' },
  { key: '快递', label: '快递', tone: 'number' },
  { key: '快递占比', label: '快递占比', tone: 'rate' },
  { key: '毛利', label: '毛利', tone: 'number' },
  { key: '毛利率', label: '毛利率', tone: 'rate' },
  { key: '推广费', label: '推广费', tone: 'number' },
  { key: '推广费占比', label: '推广占比', tone: 'rate' },
  { key: '平台利润', label: '平台利润', tone: 'number' },
  { key: '利润率', label: '利润率', tone: 'rate' },
];
const linkSummarySortHint = computed(() => {
  const column = linkSummaryColumns.find((item) => item.key === linkSummarySort.key);
  return `当前排序：${column?.label || '收入(万)'} ${linkSummarySort.order === 'asc' ? '升序 ↑' : '降序 ↓'} · 点击列标题切换`;
});
const linkSummaryRevenueOption = computed(() => ({
  color: [colorTokens.blue],
  tooltip: { trigger: 'axis', valueFormatter: (value) => `${formatSummaryWan(value)} 万` },
  grid: { left: 56, right: 20, top: 28, bottom: 64 },
  xAxis: { type: 'category', data: linkSummaryTopRows.value.map((row) => row.linkId), axisLabel: { color: '#718096', rotate: 35, formatter: (value) => String(value).slice(-8) }, axisLine: { lineStyle: { color: '#dbe4f0' } } },
  yAxis: { type: 'value', axisLabel: { color: '#718096', formatter: (value) => `${(Number(value || 0) / 10000).toFixed(0)}万` }, splitLine: { lineStyle: { color: '#edf2f7' } } },
  series: [{ name: '收入', type: 'bar', barMaxWidth: 28, data: linkSummaryTopRows.value.map((row) => row.revenue), itemStyle: { borderRadius: [5, 5, 0, 0] } }],
}));
const linkSummaryRateOption = computed(() => ({
  color: [colorTokens.rose, colorTokens.amber],
  tooltip: { trigger: 'axis', valueFormatter: (value) => `${Number(value || 0).toFixed(1)}%` },
  legend: { top: 0, right: 0, textStyle: { color: '#718096' } },
  grid: { left: 48, right: 20, top: 42, bottom: 64 },
  xAxis: { type: 'category', data: linkSummaryTopRows.value.map((row) => row.linkId), axisLabel: { color: '#718096', rotate: 35, formatter: (value) => String(value).slice(-8) }, axisLine: { lineStyle: { color: '#dbe4f0' } } },
  yAxis: { type: 'value', axisLabel: { color: '#718096', formatter: '{value}%' }, splitLine: { lineStyle: { color: '#edf2f7' } } },
  series: [
    { name: '利润率', type: 'bar', barMaxWidth: 22, data: linkSummaryTopRows.value.map((row) => row.profitRate), itemStyle: { borderRadius: [4, 4, 0, 0] } },
    { name: '推广占比', type: 'bar', barMaxWidth: 22, data: linkSummaryTopRows.value.map((row) => row.promotionPct), itemStyle: { borderRadius: [4, 4, 0, 0] } },
  ],
}));
const linkAlertGroups = computed(() => {
  const alerts = linkDashboard.value.alerts || {};
  const counts = linkDashboard.value.alertCounts || {};
  return [
    { key: 'a15', label: '近15天以上利润率<0', icon: '⚠️', tone: 'danger', items: alerts.a15 || [], count: counts.a15 ?? (alerts.a15 || []).length },
    { key: 'a10', label: '近10-14天利润率<0', icon: '⚠️', tone: 'warning', items: alerts.a10 || [], count: counts.a10 ?? (alerts.a10 || []).length },
    { key: 'a5', label: '近5-9天利润率<0', icon: '⚠️', tone: 'info', items: alerts.a5 || [], count: counts.a5 ?? (alerts.a5 || []).length },
  ];
});

function ratio(numerator, denominator) { return denominator ? numerator / denominator * 100 : 0; }
function formatWan(value) { return `${(Number(value || 0) / 10000).toFixed(1)} 万`; }
function formatMoney(value) { const amount = Number(value || 0); return Math.abs(amount) >= 10000 ? `${(amount / 10000).toFixed(2)} 万` : amount.toFixed(0); }
function formatTargetWan(value) { return `${Number(value || 0).toFixed(1)} 万`; }
function formatGoalValue(value, digits = 1) { return Number(value || 0).toFixed(digits); }
function formatGoalAmount(value) { return `${Number(value || 0).toFixed(1)} 万`; }
function formatPercent(value) { return `${Number(value || 0).toFixed(0)}%`; }
function brandOf(store = '') { if (store.includes('浪奇')) return '浪奇'; if (store.includes('威王')) return '威王'; if (store.includes('舒蕾')) return '舒蕾'; return '白牌'; }
function brandColor(brand) { return brandColors[brand] || brandColors.白牌; }
function progressClass(rate) { return rate >= 100 ? 'good' : rate >= 70 ? 'warn' : 'bad'; }
function formatLinkValue(value, key, row = {}) {
  if (key === '品牌') return brandOf(row['店铺名称']);
  if (value === null || value === undefined || value === '') return '—';
  if (linkPercentFields.has(key)) return `${(Number(value) * 100).toFixed(2)}%`;
  if (key === '数据日期' || key === '链接创建时间') return String(value).slice(0, 10);
  if (key === '收入') return formatWan(value);
  if (typeof value === 'number') return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(2);
  return String(value);
}
function formatSummaryWan(value) { return (Number(value || 0) / 10000).toFixed(2); }
function formatSummaryPercent(value) { return `${Number(value || 0).toFixed(1)}%`; }
function formatLinkRate(value) { return value === null || value === undefined || value === '' || Number.isNaN(Number(value)) ? '-' : `${(Number(value) * 100).toFixed(1)}%`; }
function linkRateTone(value) { if (value === null || value === undefined || value === '' || Number.isNaN(Number(value))) return 'missing'; return Number(value) < 0 ? 'negative' : 'positive'; }

const baseAxis = { axisLine: { lineStyle: { color: '#dbe4f0' } }, axisLabel: { color: '#718096' }, splitLine: { lineStyle: { color: '#edf2f7' } } };
const revenueOption = computed(() => ({ color: [colorTokens.blue, colorTokens.teal], tooltip: { trigger: 'axis', valueFormatter: (v) => formatWan(v) }, legend: { top: 0, right: 0, textStyle: { color: '#718096' } }, grid: { left: 46, right: 20, top: 42, bottom: 30 }, xAxis: { type: 'category', data: filteredDays.value.map((d) => String(d.date).slice(5, 10)), ...baseAxis }, yAxis: { type: 'value', ...baseAxis, axisLabel: { color: '#718096', formatter: (v) => `${(v / 10000).toFixed(0)}万` } }, series: [{ name: '收入', type: 'line', smooth: true, showSymbol: false, data: filteredDays.value.map((d) => d.revenue), areaStyle: { color: 'rgba(95,132,173,.12)' } }, { name: '平台利润', type: 'line', smooth: true, showSymbol: false, data: filteredDays.value.map((d) => d.profit) }] }));
const profitRateOption = computed(() => ({ color: [colorTokens.blue], tooltip: { trigger: 'axis', valueFormatter: (v) => `${Number(v).toFixed(1)}%` }, grid: { left: 46, right: 20, top: 24, bottom: 30 }, xAxis: { type: 'category', data: filteredDays.value.map((d) => String(d.date).slice(5, 10)), ...baseAxis }, yAxis: { type: 'value', ...baseAxis, axisLabel: { formatter: '{value}%' } }, series: [{ type: 'line', smooth: true, showSymbol: false, data: filteredDays.value.map((d) => ratio(d.profit, d.revenue)), markLine: { silent: true, data: [{ yAxis: 0 }], lineStyle: { color: '#cbd5e1' } } }] }));
const overviewPersonColors = [colorTokens.pink, colorTokens.blue, colorTokens.green, colorTokens.amber, colorTokens.purple, colorTokens.teal];
const overviewRevenueOption = computed(() => ({
  color: [colorTokens.blue, colorTokens.terracotta],
  tooltip: { trigger: 'axis', formatter: (params) => params.map((item) => `${item.marker}${item.seriesName}: ${item.seriesName.includes('收入') ? `${Number(item.value || 0).toLocaleString()} 元` : `${Number(item.value || 0).toFixed(1)}%`}`).join('<br/>') },
  legend: { top: 0, right: 0, textStyle: { color: '#718096' } },
  grid: { left: 64, right: 58, top: 42, bottom: 34 },
  xAxis: { type: 'category', data: filteredDays.value.map((d) => String(d.date).slice(5, 10)), ...baseAxis },
  yAxis: [{ type: 'value', name: '收入(元)', ...baseAxis, axisLabel: { formatter: (v) => `${(v / 10000).toFixed(0)}万` } }, { type: 'value', name: '利润率(%)', ...baseAxis, axisLabel: { formatter: '{value}%' }, splitLine: { show: false } }],
  series: [{ name: '收入(元)', type: 'bar', yAxisIndex: 0, data: filteredDays.value.map((d) => d.revenue), barMaxWidth: 30, itemStyle: { borderRadius: [5, 5, 0, 0] } }, { name: '利润率(%)', type: 'line', yAxisIndex: 1, data: filteredDays.value.map((d) => ratio(d.profit, d.revenue)), smooth: true, showSymbol: true, symbolSize: 5, lineStyle: { width: 3 } }],
}));
const overviewProfitRateOption = computed(() => {
  const focused = focusedProfitRateSeries.value;
  const lineAppearance = (name, color, width) => {
    const active = !focused || focused === name;
    return {
      lineStyle: { color, width, opacity: active ? 1 : 0.16 },
      itemStyle: { color, opacity: active ? 1 : 0.16 },
      z: active ? 3 : 1,
    };
  };
  const overallSeries = { name: '整体利润率', type: 'line', triggerEvent: true, data: filteredDays.value.map((d) => ratio(d.profit, d.revenue)), smooth: true, showSymbol: true, symbolSize: 5, ...lineAppearance('整体利润率', colorTokens.terracotta, 3) };
  const personSeries = showPersonLines.value ? peopleNames.value.map((name, index) => ({ name, type: 'line', triggerEvent: true, data: filteredDays.value.map((day) => { const row = data.value.dailyByPerson?.[String(day.date).slice(0, 10)]?.[name]; return row && Number(row.revenue || 0) > 0 ? ratio(Number(row.profit || 0), Number(row.revenue || 0)) : null; }), smooth: true, showSymbol: true, symbolSize: 6, ...lineAppearance(name, overviewPersonColors[index % overviewPersonColors.length], 2.5) })) : [];
  return { color: [colorTokens.terracotta, ...overviewPersonColors], tooltip: { trigger: 'axis', valueFormatter: (v) => `${Number(v || 0).toFixed(1)}%` }, legend: { top: 0, right: 0, textStyle: { color: '#718096' } }, grid: { left: 46, right: 20, top: 42, bottom: 34 }, xAxis: { type: 'category', data: filteredDays.value.map((d) => String(d.date).slice(5, 10)), ...baseAxis }, yAxis: { type: 'value', ...baseAxis, axisLabel: { formatter: '{value}%' }, min: (value) => Math.min(0, Math.floor(value.min - 2)) }, series: [overallSeries, ...personSeries] };
});
const personRevenueOption = computed(() => ({ color: [colorTokens.blue, colorTokens.terracotta], tooltip: { trigger: 'axis', formatter: (params) => params.map((item) => `${item.marker}${item.seriesName}: ${item.seriesName.includes('收入') ? `${Number(item.value || 0).toLocaleString()} 元` : `${Number(item.value || 0).toFixed(1)}%`}`).join('<br/>') }, legend: { top: 0, right: 0, textStyle: { color: '#718096' } }, grid: { left: 64, right: 58, top: 42, bottom: 36 }, xAxis: { type: 'category', data: peopleRows.value.map((p) => p.name), ...baseAxis }, yAxis: [{ type: 'value', name: '收入(元)', ...baseAxis, axisLabel: { formatter: (v) => `${(v / 10000).toFixed(0)}万` } }, { type: 'value', name: '利润率(%)', ...baseAxis, axisLabel: { formatter: '{value}%' }, splitLine: { show: false } }], series: [{ name: '收入(元)', type: 'bar', yAxisIndex: 0, barMaxWidth: 34, data: peopleRows.value.map((p) => p.revenue), itemStyle: { borderRadius: [5, 5, 0, 0] } }, { name: '利润率(%)', type: 'line', yAxisIndex: 1, data: peopleRows.value.map((p) => p.profitRate), smooth: true, showSymbol: true, symbolSize: 6, lineStyle: { width: 3 } }] }));
const personMarginOption = computed(() => ({ color: [colorTokens.green, colorTokens.rose], tooltip: { trigger: 'axis', valueFormatter: (v) => `${Number(v || 0).toFixed(1)}%` }, legend: { top: 0, right: 0, textStyle: { color: '#718096' } }, grid: { left: 54, right: 54, top: 42, bottom: 36 }, xAxis: { type: 'category', data: peopleRows.value.map((p) => p.name), ...baseAxis }, yAxis: [{ type: 'value', name: '毛利率(%)', ...baseAxis, axisLabel: { formatter: '{value}%' } }, { type: 'value', name: '利润率(%)', ...baseAxis, axisLabel: { formatter: '{value}%' }, splitLine: { show: false } }], series: [{ name: '毛利率(%)', type: 'bar', yAxisIndex: 0, barMaxWidth: 34, data: peopleRows.value.map((p) => p.grossMargin), itemStyle: { borderRadius: [5, 5, 0, 0] } }, { name: '利润率(%)', type: 'line', yAxisIndex: 1, data: peopleRows.value.map((p) => p.profitRate), smooth: true, showSymbol: true, symbolSize: 6, lineStyle: { width: 3 } }] }));
const personPromotionOption = computed(() => {
  const rows = [...peopleRows.value].sort((a, b) => b.promotionPct - a.promotionPct);
  return { color: [colorTokens.rose], tooltip: { trigger: 'axis', valueFormatter: (v) => `${Number(v || 0).toFixed(1)}%` }, grid: { left: 76, right: 28, top: 18, bottom: 32 }, xAxis: { type: 'value', ...baseAxis, axisLabel: { formatter: '{value}%' } }, yAxis: { type: 'category', inverse: true, data: rows.map((p) => p.name), axisLabel: { color: '#52647a' } }, series: [{ name: '推广费占比(%)', type: 'bar', data: rows.map((p) => p.promotionPct), barMaxWidth: 22, itemStyle: { borderRadius: [0, 5, 5, 0], color: (params) => { const value = Number(params.value || 0); return value >= 40 ? colorTokens.rose : value >= 25 ? colorTokens.amber : colorTokens.green; } } }] };
});
const storeRevenueOption = computed(() => {
  const rows = storeRows.value.slice(0, 15);
  return {
    tooltip: { trigger: 'axis', valueFormatter: (v) => `${formatMoney(v)} 元` },
    grid: { left: 122, right: 26, top: 18, bottom: 24 },
    xAxis: { type: 'value', ...baseAxis, axisLabel: { formatter: (v) => formatMoney(v) } },
    yAxis: { type: 'category', inverse: true, data: rows.map((s) => s.store), axisLabel: { color: '#52647a', width: 108, overflow: 'truncate' } },
    series: [{ name: '收入(元)', type: 'bar', data: rows.map((row) => ({ value: row.revenue, itemStyle: { color: brandColor(brandOf(row.store)) } })), barMaxWidth: 20, itemStyle: { borderRadius: [0, 5, 5, 0] } }],
  };
});
const storeQuadrantOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: (params) => { const row = params.data?.row || {}; return `${row.store || '店铺'}<br/>负责人：${row.person || '—'}<br/>毛利率：${Number(row.grossMargin || 0).toFixed(1)}%<br/>利润率：${Number(row.profitRate || 0).toFixed(1)}%<br/>收入：${formatMoney(row.revenue)} 元`; } },
  grid: { left: 54, right: 22, top: 24, bottom: 42 },
  xAxis: { type: 'value', name: '毛利率(%)', ...baseAxis, axisLabel: { formatter: '{value}%' } },
  yAxis: { type: 'value', name: '利润率(%)', ...baseAxis, axisLabel: { formatter: '{value}%' } },
  series: [{ name: '店铺', type: 'scatter', data: storeQuadrantRows.value.map((row) => ({ value: [row.grossMargin, row.profitRate, row.revenue], row })), symbolSize: (value) => Math.max(8, Math.min(26, Math.sqrt(Number(value?.[2] || 0)) / 3)), itemStyle: { color: (params) => { const row = params.data?.row || {}; if (row.grossMargin >= 50 && row.profitRate >= 10) return colorTokens.green; if (row.profitRate < 0) return colorTokens.rose; return colorTokens.amber; }, opacity: 0.72 }, emphasis: { itemStyle: { opacity: 1, borderColor: '#52606d', borderWidth: 1 } } }],
}));
const storePromotionOption = computed(() => {
  const rows = storeRows.value.slice(0, 15);
  return {
    color: [colorTokens.green, colorTokens.rose],
    tooltip: { trigger: 'axis', valueFormatter: (v) => `${Number(v || 0).toFixed(1)}%` },
    legend: { top: 0, right: 0, textStyle: { color: '#718096' } },
    grid: { left: 54, right: 24, top: 38, bottom: 54 },
    xAxis: { type: 'category', data: rows.map((row) => row.store), axisLabel: { color: '#718096', rotate: 32, interval: 0 } },
    yAxis: { type: 'value', ...baseAxis, axisLabel: { formatter: '{value}%' } },
    series: [{ name: '毛利率(%)', type: 'bar', data: rows.map((row) => row.grossMargin), barMaxWidth: 18, itemStyle: { borderRadius: [5, 5, 0, 0] } }, { name: '推广费占比(%)', type: 'bar', data: rows.map((row) => row.promotionPct), barMaxWidth: 18, itemStyle: { borderRadius: [5, 5, 0, 0] } }],
  };
});
const storeLossOption = computed(() => ({
  tooltip: { trigger: 'axis', valueFormatter: (v) => `${Number(v || 0).toFixed(1)}%` },
  grid: { left: 122, right: 24, top: 18, bottom: 24 },
  xAxis: { type: 'value', ...baseAxis, axisLabel: { formatter: '{value}%' } },
  yAxis: { type: 'category', inverse: true, data: storeLossRows.value.map((row) => row.store), axisLabel: { color: '#52647a', width: 108, overflow: 'truncate' } },
  series: [{ name: '利润率(%)', type: 'bar', data: storeLossRows.value.map((row) => row.profitRate), barMaxWidth: 18, itemStyle: { color: colorTokens.rose, borderRadius: [0, 5, 5, 0] } }],
}));
const productTopOption = computed(() => {
  const rows = productRows.value.slice(0, 15);
  return {
    color: [colorTokens.blue, colorTokens.green],
    tooltip: { trigger: 'axis', valueFormatter: (v) => `${formatMoney(v)} 元` },
    legend: { top: 0, right: 0, textStyle: { color: '#718096' } },
    grid: { left: 150, right: 26, top: 38, bottom: 24 },
    xAxis: { type: 'value', ...baseAxis, axisLabel: { formatter: (v) => formatMoney(v) } },
    yAxis: { type: 'category', inverse: true, data: rows.map((row) => `[${row.code}] ${(row.name || '').slice(0, 12)}`), axisLabel: { color: '#52647a', width: 136, overflow: 'truncate' } },
    series: [{ name: '收入(元)', type: 'bar', data: rows.map((row) => row.revenue), barMaxWidth: 18, itemStyle: { borderRadius: [0, 5, 5, 0] } }, { name: '利润(元)', type: 'bar', data: rows.map((row) => row.platformProfit), barMaxWidth: 18, itemStyle: { borderRadius: [0, 5, 5, 0], opacity: 0.78 } }],
  };
});
const productProfitRangeOption = computed(() => {
    const colors = [colorTokens.rose, colorTokens.blue, colorTokens.green, colorTokens.amber, colorTokens.purple, colorTokens.teal, colorTokens.terracotta, colorTokens.slate, colorTokens.pink, '#16a085'];
  const dates = filteredDays.value.map((day) => String(day.date).slice(5, 10));
  const fullDates = filteredDays.value.map((day) => String(day.date).slice(0, 10));
  const focused = focusedProductProfitSeries.value;
  const lineAppearance = (name, color) => {
    const active = !focused || focused === name;
    return {
      lineStyle: { width: 2, color, opacity: active ? 1 : 0.16 },
      itemStyle: { color, opacity: active ? 1 : 0.16 },
      z: active ? 3 : 1,
    };
  };
  return {
    color: colors,
    tooltip: { trigger: 'axis', valueFormatter: (v) => `${Number(v || 0).toFixed(1)}%` },
    legend: { top: 0, right: 0, textStyle: { color: '#718096', fontSize: 10 } },
    grid: { left: 48, right: 24, top: 54, bottom: 34 },
    xAxis: { type: 'category', data: dates, ...baseAxis },
    yAxis: { type: 'value', name: '利润率(%)', ...baseAxis, axisLabel: { formatter: '{value}%' } },
    series: productProfitRangeRows.value.map((row, index) => {
      const name = `[${row.code}] ${(row.name || row.code).slice(0, 12)}`;
      return {
        name,
        type: 'line',
        data: fullDates.map((date) => { const point = row.daily[date]; return point && point.revenue > 0 ? Number((point.profit / point.revenue * 100).toFixed(1)) : null; }),
        smooth: true,
        connectNulls: true,
        showSymbol: true,
        symbolSize: 4,
        ...lineAppearance(name, colors[index]),
      };
    }),
  };
});
const productRevenueOption = computed(() => ({ color: [colorTokens.blue], tooltip: { trigger: 'axis', valueFormatter: (v) => formatWan(v) }, grid: { left: 90, right: 22, top: 18, bottom: 20 }, xAxis: { type: 'value', ...baseAxis, axisLabel: { formatter: (v) => `${(v / 10000).toFixed(0)}万` } }, yAxis: { type: 'category', inverse: true, data: productRows.value.slice(0, 15).map((p) => p.code), axisLabel: { color: '#52647a' } }, series: [{ type: 'bar', data: productRows.value.slice(0, 15).map((p) => p.revenue), barMaxWidth: 18, itemStyle: { borderRadius: [0, 4, 4, 0] } }] }));
const productRateOption = computed(() => ({ color: [colorTokens.amber], tooltip: { trigger: 'axis', valueFormatter: (v) => `${Number(v).toFixed(1)}%` }, grid: { left: 90, right: 22, top: 18, bottom: 20 }, xAxis: { type: 'value', ...baseAxis, axisLabel: { formatter: '{value}%' } }, yAxis: { type: 'category', inverse: true, data: [...productRows.value].sort((a, b) => a.profitRate - b.profitRate).slice(0, 15).map((p) => p.code), axisLabel: { color: '#52647a' } }, series: [{ type: 'bar', data: [...productRows.value].sort((a, b) => a.profitRate - b.profitRate).slice(0, 15).map((p) => p.profitRate), barMaxWidth: 18, itemStyle: { borderRadius: [0, 4, 4, 0] } }] }));
const costOption = computed(() => ({ color: [colorTokens.blue, '#a2b9d0', colorTokens.teal, colorTokens.amber, colorTokens.slate], tooltip: { trigger: 'item', valueFormatter: (v) => formatWan(v) }, legend: { bottom: 0, textStyle: { color: '#718096' } }, series: [{ type: 'pie', radius: ['48%', '72%'], center: ['50%', '46%'], label: { color: '#52647a', formatter: (params) => `${params.name}\n${Number(params.percent || 0).toFixed(1)}%` }, data: [{ name: '货品成本', value: derivedGrand.value.cost }, { name: '快递费', value: derivedGrand.value.shipping }, { name: '推广费', value: derivedGrand.value.promotion }, { name: '平台利润', value: Math.max(derivedGrand.value.profit, 0) }] }] }));
const costPersonOption = computed(() => ({ color: [colorTokens.blue, '#a2b9d0', colorTokens.teal, colorTokens.amber], tooltip: { trigger: 'axis', valueFormatter: (v) => formatWan(v) }, legend: { top: 0, right: 0, textStyle: { color: '#718096' } }, grid: { left: 42, right: 18, top: 38, bottom: 38 }, xAxis: { type: 'category', data: peopleRows.value.map((p) => p.name), ...baseAxis }, yAxis: { type: 'value', ...baseAxis, axisLabel: { formatter: (v) => `${(v / 10000).toFixed(0)}万` } }, series: [{ name: '货品成本', type: 'bar', stack: 'cost', data: peopleRows.value.map((p) => p.cost) }, { name: '快递费', type: 'bar', stack: 'cost', data: peopleRows.value.map((p) => p.shipping) }, { name: '推广费', type: 'bar', stack: 'cost', data: peopleRows.value.map((p) => p.promotion) }, { name: '平台利润', type: 'bar', stack: 'profit', data: peopleRows.value.map((p) => p.profit) }] }));
const promoProfitOption = computed(() => ({ color: [colorTokens.amber, colorTokens.blue], tooltip: { trigger: 'axis', valueFormatter: (v) => formatWan(v) }, legend: { top: 0, right: 0, textStyle: { color: '#718096' } }, grid: { left: 46, right: 18, top: 38, bottom: 38 }, xAxis: { type: 'category', data: peopleRows.value.map((p) => p.name), ...baseAxis }, yAxis: { type: 'value', ...baseAxis, axisLabel: { formatter: (v) => `${(v / 10000).toFixed(0)}万` } }, series: [{ name: '推广费', type: 'bar', data: peopleRows.value.map((p) => p.promotion) }, { name: '平台利润', type: 'bar', data: peopleRows.value.map((p) => p.profit) }] }));
const promoEfficiencyOption = computed(() => ({ color: [colorTokens.teal], tooltip: { trigger: 'axis', valueFormatter: (v) => `${Number(v).toFixed(1)} 元` }, grid: { left: 48, right: 18, top: 18, bottom: 38 }, xAxis: { type: 'category', data: peopleRows.value.map((p) => p.name), ...baseAxis }, yAxis: { type: 'value', ...baseAxis, axisLabel: { formatter: '{value} 元' } }, series: [{ type: 'bar', barMaxWidth: 32, data: peopleRows.value.map((p) => p.promotion ? p.revenue / p.promotion : 0), itemStyle: { borderRadius: [5, 5, 0, 0] } }] }));
const goalPersonOption = computed(() => ({ color: [colorTokens.blue, '#b8cadd'], tooltip: { trigger: 'axis', valueFormatter: (v) => formatGoalAmount(v) }, legend: { top: 0, right: 0, textStyle: { color: '#718096' } }, grid: { left: 46, right: 18, top: 38, bottom: 38 }, xAxis: { type: 'category', data: goalRows.value.map((r) => r.name), ...baseAxis }, yAxis: { type: 'value', ...baseAxis, axisLabel: { formatter: (v) => `${v}万` } }, series: [{ name: '实际', type: 'bar', data: goalRows.value.map((r) => r.actual) }, { name: '目标', type: 'bar', data: goalRows.value.map((r) => r.target) }] }));
const goalBrandOption = computed(() => ({ color: [colorTokens.teal, '#b9d5d0'], tooltip: { trigger: 'axis', valueFormatter: (v) => formatGoalAmount(v) }, legend: { top: 0, right: 0, textStyle: { color: '#718096' } }, grid: { left: 46, right: 18, top: 38, bottom: 38 }, xAxis: { type: 'category', data: brandRows.value.map((r) => r.name), ...baseAxis }, yAxis: { type: 'value', ...baseAxis, axisLabel: { formatter: (v) => `${v}万` } }, series: [{ name: '实际', type: 'bar', data: brandRows.value.map((r) => r.actual) }, { name: '目标', type: 'bar', data: brandRows.value.map((r) => r.target) }] }));

const DataTable = defineComponent({
  props: {
    columns: { type: Array, required: true },
    rows: { type: Array, required: true },
    sortable: { type: Boolean, default: false },
    sortKey: { type: String, default: '' },
    sortOrder: { type: String, default: 'desc' },
    rowClickable: { type: Boolean, default: false },
    rowKey: { type: String, default: 'linkId' },
    expandedKey: { type: String, default: '' },
  },
  emits: ['sort', 'row-click'],
  setup(props, { emit, slots }) {
    const header = (column) => {
      const isSortable = props.sortable && column.sortable !== false;
      const isActive = props.sortKey === column.key;
      const direction = isActive ? props.sortOrder : '';
      const arrow = isActive ? (direction === 'asc' ? '↑' : '↓') : '↕';
      if (!isSortable) return column.label;
      return h('button', {
        type: 'button',
        class: ['table-sort-button', { active: isActive }],
        title: `按${column.label}${isActive && direction === 'desc' ? '升序' : '降序'}排序`,
        'aria-label': `按${column.label}排序，当前${isActive ? (direction === 'asc' ? '升序' : '降序') : '未排序'}`,
        onClick: () => emit('sort', column.key),
      }, [h('span', {}, column.label), h('span', { class: 'table-sort-arrow', 'aria-hidden': 'true' }, arrow)]);
    };
    return () => {
      const headerCells = props.columns.map((column) => h('th', {
        key: column.key,
        class: { 'sortable-header-cell': props.sortable && column.sortable !== false },
        'aria-sort': props.sortable && props.sortKey === column.key
          ? (props.sortOrder === 'asc' ? 'ascending' : 'descending')
          : 'none',
      }, header(column)));
      const rowKey = (row, index) => String(row[props.rowKey] ?? row.code ?? row.store ?? row.name ?? row.linkId ?? index);
      const bodyRows = props.rows.length
        ? props.rows.flatMap((row, index) => {
          const key = rowKey(row, index);
          const cells = props.columns.map((column) => h('td', {
            key: column.key,
            class: column.tone,
          }, column.format ? column.format(row[column.key]) : row[column.key] ?? '—'));
          const rows = [h('tr', {
            key,
            class: { 'clickable-row': props.rowClickable, 'expanded-row': props.expandedKey === key },
            'aria-expanded': props.rowClickable ? props.expandedKey === key : undefined,
            onClick: props.rowClickable ? () => emit('row-click', row) : undefined,
          }, cells)];
          if (props.expandedKey === key && slots.expanded) {
            rows.push(h('tr', { key: `${key}-expanded`, class: 'expanded-detail-row' }, [h('td', { colSpan: props.columns.length }, slots.expanded({ row }))]));
          }
          return rows;
        })
        : [h('tr', {}, [h('td', {
          colSpan: props.columns.length,
          class: 'empty-cell',
        }, '暂无数据')])];
      return h('div', { class: 'table-scroll' }, [
        h('table', {}, [
          h('thead', {}, [h('tr', {}, headerCells)]),
          h('tbody', {}, bodyRows),
        ]),
      ]);
    };
  },
});

function focusProfitRateLine(params) {
  if (params?.componentType !== 'series' || params.seriesType !== 'line' || !params.seriesName) return;
  focusedProfitRateSeries.value = focusedProfitRateSeries.value === params.seriesName ? null : params.seriesName;
}
function focusProductProfitLine(params) {
  if (params?.componentType !== 'series' || params.seriesType !== 'line' || !params.seriesName) return;
  focusedProductProfitSeries.value = focusedProductProfitSeries.value === params.seriesName ? null : params.seriesName;
}
function switchTab(key) {
  activeTab.value = key;
  if (key === 'links') {
    if (!linkDataDateStart.value) linkDataDateStart.value = dateStart.value;
    if (!linkDataDateEnd.value) linkDataDateEnd.value = dateEnd.value;
    if (!linkDashboardRows.value.length || !links.value.length) refreshLinkViews();
  }
  if (key === 'product-management') {
    if (!linkDataDateStart.value) linkDataDateStart.value = dateStart.value;
    if (!linkDataDateEnd.value) linkDataDateEnd.value = dateEnd.value;
    if (!links.value.length) fetchLinks(1);
  }
  if (key === 'link-summary' && !linkSummaryRows.value.length) fetchLinkSummary(1);
}
function goalNodeExpanded(key) { return expandedGoalNodes.value.has(key); }
function toggleGoalNode(key) { const next = new Set(expandedGoalNodes.value); if (next.has(key)) { next.delete(key); if (key === 'root') { next.delete('brand'); next.delete('person'); } } else next.add(key); expandedGoalNodes.value = next; }
function setRange(preset) { rangePreset.value = preset; const dates = availableDates.value; if (!dates.length) return; const end = dates.at(-1); if (preset === 'all') { dateStart.value = dates[0]; dateEnd.value = end; } else if (preset === 'month') { const month = end.slice(0, 7); const inMonth = dates.filter((date) => date.startsWith(month)); dateStart.value = inMonth[0]; dateEnd.value = inMonth.at(-1); } else { const days = preset === 'yesterday' ? 1 : preset === '3d' ? 3 : preset === '14d' ? 14 : preset === '30d' ? 30 : 7; dateStart.value = dates[Math.max(0, dates.length - days)]; dateEnd.value = end; } }
function creationParams() { if (creationFilter.mode === 'custom') return { creation_start: creationFilter.start, creation_end: creationFilter.end }; return { creation_days: Math.max(1, Number(creationFilter.days || 1)) }; }
function globalFilterParams() { return { ...creationParams(), link_ids: globalFilters.link_ids.trim(), product_code: globalFilters.product_code.trim(), product_name: globalFilters.product_name.trim(), brand: globalFilters.brand, store_name: globalFilters.store_name.trim(), store_person: globalFilters.store_person }; }
async function applyRange() { if (dateStart.value > dateEnd.value) [dateStart.value, dateEnd.value] = [dateEnd.value, dateStart.value]; if (creationFilter.mode === 'custom' && creationFilter.start && creationFilter.end && creationFilter.start > creationFilter.end) [creationFilter.start, creationFilter.end] = [creationFilter.end, creationFilter.start]; linkDataDateStart.value = dateStart.value; linkDataDateEnd.value = dateEnd.value; rangePreset.value = ''; await loadAll(globalFilterParams()); await refreshLinkViews(); if (activeTab.value === 'link-summary') await fetchLinkSummary(1); }
async function clearGlobalFilters() { Object.assign(globalFilters, { link_ids: '', product_code: '', product_name: '', brand: '', store_name: '', store_person: '' }); Object.assign(creationFilter, { mode: 'age', days: 30, start: '', end: '' }); expandedLinkSummaryId.value = ''; linkSummaryDailyRows.value = []; linkSummaryDailyError.value = ''; await applyRange(); }
function loadTargetForm() { const source = activeTarget.value || {}; targetForm.monthTarget = Number(source.monthTarget || 0); targetForm.profitRate = Number(source.profitRate || 0); targetForm.persons = { ...(source.persons || {}) }; targetForm.brands = { ...(source.brands || {}) }; }
async function saveCurrentTargets() { savingTargets.value = true; targetMessage.value = ''; try { await saveTargets(activeMonth.value, { monthTarget: targetForm.monthTarget || '', profitRate: targetForm.profitRate || '', persons: targetForm.persons, brands: targetForm.brands }); targetMessage.value = '已保存并同步到 API'; } catch (err) { targetMessage.value = err.message; } finally { savingTargets.value = false; } }
function createStandardFilterConfig(open = true) {
  return { pageSize: 20, visibleFields: null, filters: [], open, columnsOpen: false, previewRows: [], previewMeta: { total: 0, page: 1, pages: 0, size: 20 }, message: '', querying: false };
}
function normalizeStandardFilterConfig(source = {}, legacy = {}) {
  const raw = source && typeof source === 'object' ? source : {};
  const filters = Array.isArray(raw.filters) ? raw.filters.map((filter, index) => ({ id: filter.id || `standard-${Date.now()}-${index}`, field: filter.field || '', op: filter.op || 'contains', v1: filter.v1 || '', v2: filter.v2 || '' })) : [];
  const addLegacyFilter = (field, value) => {
    if (value && !filters.some((filter) => filter.field === field)) filters.unshift({ id: `standard-legacy-${Date.now()}-${field}`, field, op: 'contains', v1: value, v2: '' });
  };
  addLegacyFilter('链接id', raw.linkIds);
  addLegacyFilter('品牌', legacy.brand);
  addLegacyFilter('商品编码', legacy.productCode);
  addLegacyFilter('商品名称', legacy.productName);
  if ((raw.dateStart || raw.dateEnd) && !filters.some((filter) => filter.field === '链接创建时间')) filters.unshift({ id: `standard-legacy-${Date.now()}-creation`, field: '链接创建时间', op: 'between', v1: raw.dateStart || '', v2: raw.dateEnd || '' });
  return {
    ...createStandardFilterConfig(false),
    pageSize: Number(raw.pageSize || 20),
    visibleFields: Array.isArray(raw.visibleFields) ? [...raw.visibleFields] : null,
    filters,
    open: Boolean(raw.open),
    columnsOpen: false,
    previewRows: [],
    previewMeta: { total: 0, page: 1, pages: 0, size: Number(raw.pageSize || 20) },
    message: '',
    querying: false,
  };
}
function serializeStandardFilterConfig(config = {}) {
  return { pageSize: Number(config.pageSize || 20), visibleFields: config.visibleFields === null ? null : [...(config.visibleFields || [])], filters: (config.filters || []).map(({ field, op, v1, v2 }) => ({ field, op, v1, v2 })) };
}
function addStandardRow() { standardRows.value.push({ _key: `new-${Date.now()}`, dimensionType: 'brand', brand: '', productCode: '', productName: '', metricKey: 'profitRate', operator: 'gte', thresholdMin: 0, thresholdMax: null, enabled: true, note: '', filterConfig: createStandardFilterConfig(true) }); }
async function saveStandardRow(row) { row.saving = true; try { const payload = { ...row, brand: '', productCode: '', productName: '', filterConfig: serializeStandardFilterConfig(row.filterConfig) }; delete payload._key; delete payload.saving; await saveStandard(payload); } catch (err) { window.alert(err.message || '标准保存失败'); } finally { row.saving = false; } }
async function removeStandardRow(row) { if (!row.id) { standardRows.value = standardRows.value.filter((item) => item !== row); return; } if (!window.confirm('确认删除这条链接设置？')) return; try { await deleteStandard(row.id); } catch (err) { window.alert(err.message || '标准删除失败'); } }
async function fetchLinks(page = 1) {
  const activeFilters = activeLinkFilters.value;
  await loadLinks({
    page,
    size: linkQuery.size,
    start: linkDataDateStart.value || dateStart.value,
    end: linkDataDateEnd.value || dateEnd.value,
    search: linkQuery.search,
    link_ids: [globalFilters.link_ids, linkDataLinkIds.value].filter(Boolean).join(','),
    product_code: globalFilters.product_code,
    product_name: globalFilters.product_name,
    brand: globalFilters.brand,
    store_name: globalFilters.store_name,
    store_person: globalFilters.store_person || linkQuery.store_person,
    ...creationParams(),
    profit_rate_lte: linkQuery.profit_rate_lte,
    filter_json: activeFilters.length ? JSON.stringify(activeFilters) : '',
  });
  selectedLinks.value = [];
}
async function fetchLinkDashboard(page = 1) { await loadLinkDashboard({ page, size: linkQuery.size, start: dateStart.value, end: dateEnd.value, search: linkQuery.search, link_ids: globalFilters.link_ids, product_code: globalFilters.product_code, product_name: globalFilters.product_name, brand: globalFilters.brand, store_name: globalFilters.store_name, store_person: globalFilters.store_person, ...creationParams() }); }
function changeLinkSummarySort(key) {
  const column = linkSummaryColumns.find((item) => item.key === key);
  if (!column) return;
  if (linkSummarySort.key === key) linkSummarySort.order = linkSummarySort.order === 'asc' ? 'desc' : 'asc';
  else { linkSummarySort.key = key; linkSummarySort.order = 'desc'; }
  fetchLinkSummary(1);
}
async function fetchLinkSummary(page = 1) { await loadLinkSummary({ page, size: linkSummaryQuery.size, start: dateStart.value, end: dateEnd.value, search: linkSummaryQuery.search, link_ids: globalFilters.link_ids, product_code: globalFilters.product_code, product_name: globalFilters.product_name, brand: globalFilters.brand, store_name: globalFilters.store_name, store_person: globalFilters.store_person, sort_by: linkSummarySort.key, sort_order: linkSummarySort.order, ...creationParams() }); }
async function toggleLinkSummaryRow(row) {
  const linkId = String(row?.linkId || '').trim();
  if (!linkId) return;
  if (expandedLinkSummaryId.value === linkId) {
    expandedLinkSummaryId.value = '';
    linkSummaryDailyRows.value = [];
    linkSummaryDailyError.value = '';
    return;
  }
  expandedLinkSummaryId.value = linkId;
  linkSummaryDailyRows.value = [];
  linkSummaryDailyError.value = '';
  linkSummaryDailyLoading.value = true;
  globalFilters.link_ids = linkId;
  linkDataLinkIds.value = '';
  try {
    await applyRange();
    const result = await queryLinks({ page: 1, size: 100, start: dateStart.value, end: dateEnd.value, link_ids: linkId, ...creationParams() });
    linkSummaryDailyRows.value = result.data || [];
  } catch (err) {
    linkSummaryDailyError.value = err.message || '每日明细加载失败';
  } finally {
    linkSummaryDailyLoading.value = false;
  }
}
async function refreshLinkViews() { await Promise.all([fetchLinkDashboard(1), fetchLinks(1)]); }
function refreshLinkData() { return fetchLinks(1); }
function scheduleLinkRefresh() { window.clearTimeout(linkRefreshTimer); linkRefreshTimer = window.setTimeout(refreshLinkViews, 240); }
function scheduleProductManagementRefresh() { window.clearTimeout(linkRefreshTimer); linkRefreshTimer = window.setTimeout(refreshLinkData, 240); }
function normalizeLinkDateRange() { if (dateStart.value > dateEnd.value) [dateStart.value, dateEnd.value] = [dateEnd.value, dateStart.value]; }
function normalizeLinkDataDateRange() { if (linkDataDateStart.value && linkDataDateEnd.value && linkDataDateStart.value > linkDataDateEnd.value) [linkDataDateStart.value, linkDataDateEnd.value] = [linkDataDateEnd.value, linkDataDateStart.value]; }
function toggleLinkAlert(key) { linkAlertOpen[key] = !linkAlertOpen[key]; }
function selectLinkAlert(item) { linkQuery.search = item.id; linkDetailExpanded.value = true; refreshLinkViews(); }
function linkFilterType(filter) { return linkColumnOptions.value.find((column) => column.key === filter.field)?.type || 'text'; }
function linkFilterInputType(filter) { return linkFilterType(filter) === 'date' ? 'date' : linkFilterType(filter) === 'number' ? 'number' : 'text'; }
function linkFilterPlaceholder(filter) { return filter.field === '链接id' ? '支持逗号分隔多个链接 ID' : linkFilterType(filter) === 'text' ? '包含值' : '值'; }
function linkFilterUsesSecondValue(filter) { return linkFilterType(filter) !== 'text' && filter.op === 'between'; }
function onLinkFilterFieldChange(filter) { filter.op = linkFilterType(filter) === 'text' ? 'contains' : 'between'; filter.v1 = ''; filter.v2 = ''; }
function normalizeLinkFilterOperator(filter) { if (linkFilterType(filter) === 'text') filter.op = 'contains'; if (filter.op !== 'between') filter.v2 = ''; }
function addLinkFilter() { linkFilters.push({ id: ++linkFilterId, field: '', op: 'contains', v1: '', v2: '' }); }
function removeLinkFilter(index) { linkFilters.splice(index, 1); applyLinkFilters(); }
const activeLinkFilters = computed(() => linkFilters.filter((filter) => filter.field && (filter.v1 || filter.v2)).map(({ field, op, v1, v2 }) => ({ field, op, v1, v2 })));
const linkFilterSummary = computed(() => activeLinkFilters.value.map((filter) => {
  const label = linkColumnOptions.value.find((column) => column.key === filter.field)?.label || filter.field;
  const text = filter.op === 'between' ? `${filter.v1} ~ ${filter.v2}` : filter.op === 'gte' ? `≥ ${filter.v1}` : filter.op === 'lte' ? `≤ ${filter.v1}` : `包含 ${filter.v1}`;
  return `${label} ${text}`;
}).join(' AND '));
function applyLinkFilters() { normalizeLinkDataDateRange(); refreshLinkData(); }
function clearLinkFilters() { linkFilters.splice(0); linkDataLinkIds.value = ''; applyLinkFilters(); }
function toggleLinkColumn(key, checked) {
  const allKeys = linkColumnOptions.value.map((column) => column.key);
  const selected = visibleLinkColumnKeys.value === null ? [...allKeys] : [...visibleLinkColumnKeys.value];
  if (checked && !selected.includes(key)) selected.push(key);
  if (!checked) {
    const index = selected.indexOf(key);
    if (index >= 0) selected.splice(index, 1);
  }
  visibleLinkColumnKeys.value = selected.length === allKeys.length ? null : selected;
}
function selectAllLinkColumns(checked) { visibleLinkColumnKeys.value = checked ? null : []; }
function standardFilterType(row, filter) { return linkColumnOptions.value.find((column) => column.key === filter.field)?.type || 'text'; }
function standardFilterInputType(row, filter) { const type = standardFilterType(row, filter); return type === 'date' ? 'date' : type === 'number' ? 'number' : 'text'; }
function standardFilterPlaceholder(row, filter) { return filter.field === '链接id' ? '支持逗号分隔多个链接 ID' : standardFilterType(row, filter) === 'text' ? '包含值' : '值'; }
function standardFilterUsesSecondValue(row, filter) { return standardFilterType(row, filter) !== 'text' && filter.op === 'between'; }
function onStandardFilterFieldChange(row, filter) { filter.op = standardFilterType(row, filter) === 'text' ? 'contains' : 'between'; filter.v1 = ''; filter.v2 = ''; }
function normalizeStandardFilterOperator(row, filter) { if (standardFilterType(row, filter) === 'text') filter.op = 'contains'; if (filter.op !== 'between') filter.v2 = ''; }
function addStandardFilter(row) { row.filterConfig.filters.push({ id: `standard-filter-${++standardFilterId}`, field: '', op: 'contains', v1: '', v2: '' }); }
function removeStandardFilter(row, index) { row.filterConfig.filters.splice(index, 1); }
function toggleStandardColumn(row, key, checked) { const allKeys = linkColumnOptions.value.map((column) => column.key); const selected = row.filterConfig.visibleFields === null ? [...allKeys] : [...row.filterConfig.visibleFields]; if (checked && !selected.includes(key)) selected.push(key); if (!checked) { const index = selected.indexOf(key); if (index >= 0) selected.splice(index, 1); } row.filterConfig.visibleFields = selected.length === allKeys.length ? null : selected; }
function selectAllStandardColumns(row, checked) { row.filterConfig.visibleFields = checked ? null : []; }
function standardActiveFilters(row) {
  return (row.filterConfig.filters || []).filter((filter) => filter.field && (filter.v1 || filter.v2)).map(({ field, op, v1, v2 }) => ({ field, op, v1, v2 }));
}
function standardFilterSummary(row) { return standardActiveFilters(row).map((filter) => { const label = linkColumnOptions.value.find((column) => column.key === filter.field)?.label || filter.field; const text = filter.op === 'between' ? `${filter.v1} ~ ${filter.v2}` : filter.op === 'gte' ? `≥ ${filter.v1}` : filter.op === 'lte' ? `≤ ${filter.v1}` : `包含 ${filter.v1}`; return `${label} ${text}`; }).join(' AND '); }
function standardFilterParams(row) {
  const config = row.filterConfig;
  return { page: 1, size: Number(config.pageSize || 20), start: dateStart.value, end: dateEnd.value, link_ids: globalFilters.link_ids || '', product_code: globalFilters.product_code || '', product_name: globalFilters.product_name || '', brand: globalFilters.brand || '', store_name: globalFilters.store_name || '', store_person: globalFilters.store_person || '', ...creationParams(), filter_json: JSON.stringify(standardActiveFilters(row)), aggregate: 'link_person' };
}
async function queryStandardRow(row) { const config = row.filterConfig; config.querying = true; config.message = ''; try { const result = await queryLinks(standardFilterParams(row)); config.previewRows = result.data || []; config.previewMeta = { total: result.total || 0, page: result.page || 1, pages: result.pages || 0, size: result.size || config.pageSize }; config.message = `匹配 ${Number(result.total || 0).toLocaleString()} 组`; } catch (err) { config.previewRows = []; config.previewMeta = { total: 0, page: 1, pages: 0, size: config.pageSize }; config.message = err.message || '查询失败'; } finally { config.querying = false; } }
function exportStandardRow(row) { const config = row.filterConfig; if (!config.previewRows.length) return; const selected = config.visibleFields === null ? linkColumnOptions.value : linkColumnOptions.value.filter((column) => config.visibleFields.includes(column.key)); if (!selected.length) return; const escape = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`; const header = selected.map((column) => escape(column.label)).join(','); const rows = config.previewRows.map((item) => selected.map((column) => escape(formatLinkValue(item[column.key], column.key, item))).join(',')); const blob = new Blob([`\uFEFF${[header, ...rows].join('\n')}`], { type: 'text/csv;charset=utf-8' }); const anchor = document.createElement('a'); anchor.href = URL.createObjectURL(blob); anchor.download = `link_setting_${row.id || 'draft'}_${new Date().toISOString().slice(0, 10)}.csv`; anchor.click(); URL.revokeObjectURL(anchor.href); }
function resetLinks() {
  Object.assign(linkQuery, { search: '', store_person: '', profit_rate_lte: '', size: 20 });
  linkDataLinkIds.value = '';
  linkFilters.splice(0);
  linkDataDateStart.value = dateStart.value;
  linkDataDateEnd.value = dateEnd.value;
  refreshLinkViews();
}
function exportLinksCsv() {
  if (!links.value.length || !linkColumns.value.length) return;
  const escape = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`;
  const header = linkColumns.value.map((column) => escape(column.label)).join(',');
  const rows = links.value.map((row) => linkColumns.value.map((column) => escape(formatLinkValue(row[column.key], column.key, row))).join(','));
  const blob = new Blob([`\uFEFF${[header, ...rows].join('\n')}`], { type: 'text/csv;charset=utf-8' });
  const anchor = document.createElement('a');
  anchor.href = URL.createObjectURL(blob);
  anchor.download = `link_data_${new Date().toISOString().slice(0, 10)}.csv`;
  anchor.click();
  URL.revokeObjectURL(anchor.href);
}
const allLinksSelected = computed(() => links.value.length > 0 && links.value.every((row) => selectedLinks.value.includes(row['链接id'])));
function toggleAllLinks(event) { selectedLinks.value = event.target.checked ? links.value.map((row) => row['链接id']) : []; }
async function submitSelectedLinks() { if (!selectedLinks.value.length) return; const stores = links.value.filter((row) => selectedLinks.value.includes(row['链接id'])).map((row) => row['店铺名称']).filter(Boolean); const response = await submitDelist({ task_type: 'delist', operation: 'delist', operation_type: 'delist', operation_name: '产品下架', operation_label: '产品下架', link_ids: selectedLinks.value, store_names: [...new Set(stores)], operator: '链接监控' }); window.alert(response?.success ? `已提交 ${selectedLinks.value.length} 条下架任务` : response?.error || '提交失败'); selectedLinks.value = []; }
const selectedLinkRows = computed(() => selectedLinks.value.map((linkId) => {
  const row = links.value.find((item) => String(item['链接id']) === String(linkId));
  return { linkId, storeName: row?.['店铺名称'] || '' };
}));
function openPromotionAdjust() {
  if (!selectedLinks.value.length) return;
  adjustPreset.value = 0.05;
  adjustMessage.value = '';
  adjustModalOpen.value = true;
}
function closePromotionAdjust() {
  if (!adjustingPromotion.value) adjustModalOpen.value = false;
}
async function submitPromotionAdjust() {
  const preset = promotionAdjustPresets.find((item) => item.value === adjustPreset.value);
  if (!preset) {
    adjustMessage.value = '请选择投产调整档次';
    return;
  }
  const value = preset.value;
  adjustingPromotion.value = true;
  adjustMessage.value = '';
  try {
    const response = await sendPromotionAdjust({
      task_type: 'promotion_adjust',
      operation: 'promotion_adjust',
      operation_type: 'promotion_adjust',
      operation_name: '调整投产',
      operation_label: `${preset.label} ${preset.display}`,
      adjustment_preset_key: preset.key,
      adjustment_label: preset.label,
      adjustment_display: preset.display,
      link_ids: [...selectedLinks.value],
      store_names: selectedLinkRows.value.map((item) => item.storeName),
      direction: 'up',
      value,
      operator: '链接监控',
    });
    if (!response?.success) throw new Error(response?.error || '调整投产提交失败');
    adjustModalOpen.value = false;
    window.alert(`已提交 ${selectedLinks.value.length} 条调整投产任务`);
    selectedLinks.value = [];
  } catch (err) {
    adjustMessage.value = err.message || '调整投产提交失败';
  } finally {
    adjustingPromotion.value = false;
  }
}

watch([availableDates, targetMonths], () => {
  if (!dateStart.value && availableDates.value.length) setRange('month');
  if (!linkDataDateStart.value && dateStart.value) linkDataDateStart.value = dateStart.value;
  if (!linkDataDateEnd.value && dateEnd.value) linkDataDateEnd.value = dateEnd.value;
  const dataMonth = availableDates.value.at(-1)?.slice(0, 7);
  if (dataMonth && activeMonth.value !== dataMonth) {
    activeMonth.value = dataMonth;
    loadTargetForm();
  } else if (!activeMonth.value && targetMonths.value.length) {
    activeMonth.value = targetMonths.value.at(-1);
    loadTargetForm();
  }
});
watch([dateStart, dateEnd], () => {
  if (activeTab.value === 'links' && dateStart.value && dateEnd.value) scheduleLinkRefresh();
  if (activeTab.value === 'product-management' && dateStart.value && dateEnd.value) scheduleProductManagementRefresh();
});
watch(showPersonLines, (visible) => {
  if (!visible && focusedProfitRateSeries.value && focusedProfitRateSeries.value !== '整体利润率') focusedProfitRateSeries.value = null;
});
watch(productProfitRangeRows, (rows) => {
  if (focusedProductProfitSeries.value && !rows.some((row) => `[${row.code}] ${(row.name || row.code).slice(0, 12)}` === focusedProductProfitSeries.value)) {
    focusedProductProfitSeries.value = null;
  }
}, { deep: true });
watch(standards, (rows) => {
  standardRows.value = (rows || []).map((row) => ({ ...row, brand: '', productCode: '', productName: '', filterConfig: normalizeStandardFilterConfig(row.filterConfig, row), _key: `standard-${row.id}` }));
}, { deep: true, immediate: true });
onMounted(() => loadAll(globalFilterParams()));
</script>
