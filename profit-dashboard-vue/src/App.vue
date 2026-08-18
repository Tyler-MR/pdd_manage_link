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
              <label>单量 <input v-model="globalFilters.orders" type="number" min="0" step="1" inputmode="numeric" placeholder="请输入单量" title="按当前日期范围汇总后的单量精确筛选" /></label>
              <label>品牌 <select v-model="globalFilters.brand"><option value="">全部品牌</option><option v-for="brand in brandOptions" :key="brand" :value="brand">{{ brand }}</option></select></label>
              <label>店铺名称 <input v-model="globalFilters.store_name" placeholder="输入店铺名称" /></label>
              <label>负责人 <select v-model="globalFilters.store_person"><option value="">全部负责人</option><option v-for="person in peopleNames" :key="person" :value="person">{{ person }}</option></select></label>
               <label class="link-preset-filter">链接筛选
                 <select v-model="activeLinkPresetId" :disabled="!linkFilterPresets.length" title="选择管理中台已保存的链接筛选条件" @change="applyLinkPreset">
                   <option value="">全部链接</option>
                   <option v-for="preset in linkFilterPresets" :key="preset.id" :value="preset.id">{{ preset.label }}</option>
                 </select>
               </label>
               <label>商品状态
                 <select v-model="globalFilters.sale_status" title="按最新链接信息快照筛选在售或已下架商品">
                   <option value="">全部状态</option>
                   <option value="在售">在售</option>
                   <option value="已下架">已下架</option>
                 </select>
               </label>
           <button class="button primary compact" :disabled="loading" @click="applyRange">{{ loading ? '加载中…' : '搜索' }}</button>
              <button class="button secondary compact" :disabled="loading" @click="clearGlobalFilters">清除筛选</button>
              <button class="button adjust compact" :disabled="promotionDimension !== 'link' || !selectedOperationIds.length" title="对当前已勾选链接调整投产" @click="openPromotionAdjust">📊 调整投产</button>
              <button class="button danger compact" :disabled="promotionDimension !== 'link' || !selectedOperationIds.length" title="下架当前已勾选链接" @click="openDelistConfirm">📦 产品下架</button>
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

        <section v-else-if="activeTab === 'promotion'" class="promotion-page">
          <section class="panel promotion-intro-panel">
            <div class="promotion-intro-copy">
              <div class="promotion-title-line"><span class="promotion-app-icon">P</span><div><span class="promotion-kicker">商品推广</span><h2>商品推广数据概览</h2></div></div>
  <p>查看链接信息、利润日汇总和推广日级数据；页面筛选统一使用顶部的全局筛选器。</p>
            </div>
            <div class="promotion-intro-actions">
              <button type="button" class="text-button" @click="promotionHelpOpen = true">产品介绍</button>
              <button type="button" class="button secondary compact" @click="promotionDataSummaryOpen = !promotionDataSummaryOpen">{{ promotionDataSummaryOpen ? '收起数据概览' : '查看全部数据' }}</button>
            </div>
          </section>

          <section class="promotion-kpi-shell" aria-label="推广指标卡片">
            <button type="button" class="promotion-kpi-arrow" aria-label="向左查看指标" @click="scrollPromotionKpis(-1)">‹</button>
            <div ref="promotionKpiTrack" class="promotion-kpi-track">
              <button v-for="card in orderedPromotionCards(promotionKpiCards)" :key="card.key" type="button" class="promotion-kpi-card" :class="{ active: promotionTrendOpen && promotionSelectedKpi === card.key, 'is-dragging': promotionCardDragKey === card.key }" :aria-pressed="promotionTrendOpen && promotionSelectedKpi === card.key" :title="`拖动调整${card.label}卡片顺序`" @click="handlePromotionCardClick($event, card.key)" @pointerdown="startPromotionCardPointerDrag($event, card.key)" @pointerenter="handlePromotionCardPointerEnter(card.key)" @pointermove="handlePromotionCardPointerEnter(card.key)" @mouseenter="handlePromotionCardPointerEnter(card.key)" @pointerup="endPromotionCardPointerDrag" @pointercancel="endPromotionCardPointerDrag">
                <span>{{ card.label }}</span><strong>{{ card.value }}</strong><em>{{ card.note }}</em>
              </button>
            </div>
            <button type="button" class="promotion-kpi-arrow" aria-label="向右查看指标" @click="scrollPromotionKpis(1)">›</button>
          </section>

          <!-- 走势详情已迁移到右侧数据总览抽屉 -->
          <section v-if="false" class="panel promotion-trend-panel">
            <div class="promotion-trend-heading"><div><strong>{{ promotionSelectedKpiCard.label }}走势</strong><span>{{ promotionRangeHint }} · 点击上方指标卡切换</span></div><div class="promotion-trend-heading-actions"><span class="promotion-trend-value">{{ promotionSelectedKpiCard.value }}</span><button type="button" class="text-button promotion-trend-close" aria-label="关闭走势面板" @click="promotionTrendOpen = false">收起</button></div></div>
            <div v-if="promotionTrendRows.length" class="promotion-trend-chart">
              <svg viewBox="0 0 900 230" role="img" :aria-label="`${promotionSelectedKpiCard.label}趋势图`" preserveAspectRatio="none">
                <line v-for="line in promotionTrendGridLines" :key="line.y" x1="0" :y1="line.y" x2="900" :y2="line.y" class="promotion-trend-grid-line" />
                <polyline :points="promotionTrendPoints" class="promotion-trend-line" />
                <circle v-for="point in promotionTrendPointsList" :key="point.key" :cx="point.x" :cy="point.y" r="3.5" class="promotion-trend-point"><title>{{ point.label }}：{{ point.display }}</title></circle>
              </svg>
              <div class="promotion-trend-axis"><span>{{ promotionTrendRows[0].date }}</span><span>{{ promotionTrendRows[Math.floor(promotionTrendRows.length / 2)].date }}</span><span>{{ promotionTrendRows.at(-1).date }}</span></div>
            </div>
            <div v-else class="promotion-trend-empty">当前筛选范围暂无可展示的趋势数据</div>
          </section>

          <section v-if="promotionDataSummaryOpen" class="panel promotion-summary-panel">
            <div class="promotion-summary-head"><div><strong>链接经营数据总览</strong><span>链接信息为维度，利润按链接 ID + 负责人 + 数据日期聚合，推广按商品 ID + 数据日期 + 小时聚合。</span></div><button type="button" class="text-button" @click="promotionDataSummaryOpen = false">收起</button></div>
            <div class="promotion-summary-grid"><div><span>有效推广商品</span><strong>{{ promotionRows.length.toLocaleString() }}</strong></div><div><span>有成交商品</span><strong>{{ promotionSummary.orderedProducts.toLocaleString() }}</strong></div><div><span>平均实际投产比</span><strong>{{ promotionSummary.roi.toFixed(2) }}</strong></div><div><span>数据日期</span><strong>{{ promotionFilters.start }} 至 {{ promotionFilters.end }}</strong></div></div>
          </section>

          <section class="panel promotion-list-panel">
            <div class="panel-heading promotion-list-heading"><div><h2>链接经营明细</h2><p>按{{ promotionDimensionLabel }}维度汇总链接信息、利润日数据与推广日数据；点击“数据”查看每日明细</p></div><div class="promotion-list-actions"><button type="button" class="button secondary compact" @click="openPromotionColumnConfig">字段设置</button><button type="button" class="button secondary compact" @click="promotionReportOpen = true">报表说明</button></div></div>
            <div class="promotion-dimension-tabs" role="tablist" aria-label="多维度查看">
              <button v-for="dimension in promotionDimensions" :key="dimension.key" type="button" role="tab" class="promotion-dimension-tab" :class="{ active: promotionDimension === dimension.key }" :aria-selected="promotionDimension === dimension.key" @click="setPromotionDimension(dimension.key)">{{ dimension.label }}</button>
            </div>
            <div v-if="promotionColumnsOpen" class="promotion-columns-backdrop" @click.self="cancelPromotionColumnConfig">
              <section class="promotion-columns-dialog panel" role="dialog" aria-modal="true" aria-labelledby="promotion-columns-title">
                <div class="promotion-columns-dialog-head"><div><span class="promotion-columns-kicker">CUSTOM DATA ITEMS</span><h2 id="promotion-columns-title">自定义数据项</h2><p>选择表格字段，并在右侧调整展示顺序。</p></div><button type="button" class="modal-close" aria-label="关闭字段设置" @click="cancelPromotionColumnConfig">×</button></div>
                <div class="promotion-columns-dialog-body">
                  <section class="promotion-columns-available"><div class="promotion-columns-section-head"><strong>可选数据项</strong><label class="promotion-columns-search"><input v-model="promotionColumnSearch" type="search" placeholder="请输入字段名称" /><span aria-hidden="true">⌕</span></label></div><div class="promotion-columns-groups"><div v-for="group in promotionColumnGroups" :key="group.key" class="promotion-column-group"><strong class="promotion-column-group-title"><input type="checkbox" :checked="group.keys.every((key) => promotionColumnDraft.includes(key))" @change="togglePromotionColumnGroup(group)" /> {{ group.label }}</strong><div class="promotion-column-option-grid"><label v-for="column in group.columns" :key="column.key" class="promotion-column-option"><input type="checkbox" :checked="promotionColumnDraft.includes(column.key)" @change="togglePromotionColumnDraft(column.key)" /><span>{{ column.label }}</span></label></div></div><p v-if="!promotionColumnGroups.some((group) => group.columns.length)" class="empty-cell">没有匹配的字段</p></div></section>
                  <section class="promotion-columns-selected"><div class="promotion-columns-section-head"><strong>已选 <b>{{ promotionColumnDraft.length }}</b> 项数据</strong><button type="button" class="text-button" @click="restorePromotionColumns">恢复默认</button></div><p class="promotion-columns-tip">拖动字段右侧的手柄调整顺序</p><div class="promotion-selected-list"><div v-for="(column, index) in promotionDraftColumns" :key="column.key" class="promotion-selected-item" draggable="true" @dragstart="startPromotionColumnDrag(column.key)" @dragover.prevent @drop="dropPromotionColumn(column.key)"><span class="promotion-drag-handle" aria-hidden="true">⠿</span><span class="promotion-selected-index">{{ index + 1 }}</span><span class="promotion-selected-label">{{ column.label }}</span><div class="promotion-selected-actions"><button type="button" :disabled="index === 0" :aria-label="`上移${column.label}`" @click="movePromotionColumn(index, -1)">↑</button><button type="button" :disabled="index === promotionDraftColumns.length - 1" :aria-label="`下移${column.label}`" @click="movePromotionColumn(index, 1)">↓</button><button type="button" :aria-label="`移除${column.label}`" @click="removePromotionColumn(column.key)">×</button></div></div><p v-if="!promotionDraftColumns.length" class="promotion-columns-empty">请至少选择一个字段</p></div></section>
                </div>
                <div class="promotion-columns-dialog-foot"><button type="button" class="button secondary" @click="cancelPromotionColumnConfig">取消</button><button type="button" class="button secondary" @click="savePromotionColumnTemplate">保存为模板</button><button type="button" class="button primary" @click="applyPromotionColumnConfig">确定</button></div>
              </section>
            </div>
            <div class="promotion-table-scroll"><table class="promotion-table"><thead><tr><th><input type="checkbox" :checked="allPromotionSelected" :disabled="promotionDimension !== 'link'" aria-label="全选当前筛选结果" title="全选当前筛选结果（包含所有分页）" @change="toggleAllPromotion" /></th><th v-for="column in visiblePromotionColumns" :key="column.key" :class="{ 'promotion-sortable-header': column.sortable !== false }" :aria-sort="promotionSort.key === column.key ? (promotionSort.order === 'asc' ? 'ascending' : 'descending') : 'none'"><button v-if="column.sortable !== false" type="button" class="promotion-sort-button" :class="{ active: promotionSort.key === column.key }" :title="`按${column.label}排序：第一次点击升序，再次点击降序`" @click="changePromotionSort(column.key)"><span>{{ column.label }}</span><span class="promotion-sort-arrow" aria-hidden="true">{{ promotionSort.key === column.key ? (promotionSort.order === 'asc' ? '↑' : '↓') : '↕' }}</span></button><span v-else>{{ column.label }}</span></th><th>操作</th></tr></thead><tbody><template v-for="row in pagedPromotionRows" :key="row.linkId"><tr :class="{ 'promotion-row-active': promotionExpandedKey === row.linkId }" @click="openPromotionRowDrawer(row)"><td><input v-model="selectedPromotionIds" type="checkbox" :value="row.linkId" :disabled="promotionDimension !== 'link'" :aria-label="`选择链接 ${row.linkId}`" @click.stop /></td><td v-for="column in visiblePromotionColumns" :key="column.key" :class="column.tone"><template v-if="column.key === 'imageUrl'"><button v-if="row.imageUrl" type="button" class="promotion-image-preview-button" :aria-label="`放大查看${row.title || '链接主图'}`" @click.stop="openPromotionImagePreview(row.imageUrl)"><img :src="row.imageUrl" class="promotion-link-thumb" alt="链接主图" /></button><span v-else>—</span></template><template v-else>{{ formatPromotionValue(row[column.key], column) }}</template></td><td class="promotion-row-actions"><button type="button" class="promotion-link-button" @click.stop="togglePromotionDetails(row, 'detail')">详情</button><button type="button" class="promotion-link-button" :disabled="promotionDimension !== 'link'" :title="promotionDimension === 'link' ? '查看每日推广数据' : '请切换到链接维度查看每日推广数据'" @click.stop="togglePromotionDetails(row, 'data')">数据</button><button type="button" class="promotion-link-button" @click.stop="togglePromotionDetails(row, 'more')">更多</button></td></tr><tr v-if="promotionExpandedKey === row.linkId" class="promotion-expanded-row"><td :colspan="visiblePromotionColumns.length + 2"><div class="promotion-expanded-panel"><div class="promotion-expanded-head"><div><strong>{{ promotionExpandedModeLabel }} · {{ row.title }}</strong><span>链接 ID：{{ row.linkId }} · {{ row.brand }} · {{ row.person }}</span></div><button type="button" class="icon-button" aria-label="关闭详情" @click="closePromotionDetails">×</button></div><div v-if="promotionExpandedMode === 'detail'" class="promotion-detail-grid"><div><span>商品编码</span><strong>{{ row.productCode || '—' }}</strong></div><div><span>推广状态</span><strong>{{ row.status }}</strong></div><div><span>推广阶段</span><strong>{{ row.stage }}</strong></div><div><span>净目标投产比</span><strong>{{ row.targetRoi == null ? '—' : Number(row.targetRoi).toFixed(2) }}</strong></div></div><div v-else-if="promotionExpandedMode === 'data'" class="promotion-data-panel"><div class="promotion-hourly-head"><div><strong>分天数据</strong><span>源数据粒度：数据日期</span></div><div class="promotion-hourly-controls"><label>数据日期<select class="promotion-hour-date-select" v-model="promotionHourDate"><option value="all">全部数据日期</option><option v-for="date in promotionHourlyDates" :key="date" :value="date">{{ date }}</option></select></label></div></div><div class="promotion-mini-metrics"><span>当前日期<strong>{{ promotionHourDate === 'all' ? '全部' : promotionHourDate }}</strong></span><span>源数据行<strong>{{ promotionHourlyRows.length.toLocaleString() }}</strong></span><span>当前筛选范围<strong>{{ promotionFilters.start }} 至 {{ promotionFilters.end }}</strong></span></div><div v-if="promotionHourlyLoading" class="empty-cell">正在加载真实推广日数据…</div><div v-else-if="promotionHourlyError" class="empty-cell">{{ promotionHourlyError }}</div><div v-else class="promotion-hourly-table-scroll"><table class="promotion-hourly-table"><thead><tr><th>数据日期</th><th>曝光量</th><th>点击量</th><th>成交笔数</th><th>花费(元)</th><th>交易额(元)</th><th>投产比</th></tr></thead><tbody><tr v-for="item in promotionHourlyRows" :key="`${item.date}-${item.hour}-${item.productId}`"><td>{{ item.date }}</td><td>{{ Number(item.impressions || 0).toLocaleString() }}</td><td>{{ Number(item.clicks || 0).toLocaleString() }}</td><td>{{ Number(item.orders || 0).toLocaleString() }}</td><td>{{ Number(item.spend || 0).toFixed(2) }}</td><td>{{ Number(item.revenue || 0).toFixed(2) }}</td><td :class="row.targetRoi != null && item.roi >= row.targetRoi ? 'rate-positive' : 'rate-neutral'">{{ Number(item.roi || 0).toFixed(2) }}</td></tr><tr v-if="!promotionHourlyRows.length"><td colspan="7" class="empty-cell">当前商品在所选日期范围内暂无推广日数据</td></tr></tbody></table></div></div><div v-else class="promotion-more-menu"><button type="button" @click="promotionNotice('已标记为重点观察')">标记为重点观察</button><button type="button" @click="promotionNotice('已打开调投产入口')">调整投产</button><button type="button" @click="promotionNotice('已复制商品 ID')">复制商品 ID</button><button type="button" class="danger" @click.stop="openRowDelistConfirm(row)">下架链接</button></div></div></td></tr></template><tr v-if="!promotionLoading && !pagedPromotionRows.length"><td :colspan="visiblePromotionColumns.length + 2" class="empty-cell">当前筛选条件下暂无推广商品</td></tr></tbody></table></div>
            <div class="promotion-table-footer"><span>第 {{ promotionPage }} / {{ promotionPages || 1 }} 页</span><label>每页<select v-model.number="promotionPageSize"><option :value="5">5 条</option><option :value="10">10 条</option><option :value="20">20 条</option></select></label><div class="link-pager"><button type="button" :disabled="promotionPage <= 1" @click="promotionPage -= 1">上一页</button><button type="button" :disabled="promotionPage >= promotionPages" @click="promotionPage += 1">下一页</button></div></div>
          </section>
        </section>

        <section v-else-if="activeTab !== 'admin' && activeTab !== 'analysis' && activeTab !== 'product-management'" class="kpi-grid">
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

        <section v-if="false && activeTab === 'promotion'" class="link-section">
          <section v-if="activeTab === 'promotion'" class="panel link-detail-panel">
            <div class="link-detail-header">
              <button type="button" class="link-detail-title" :aria-expanded="linkDetailExpanded" title="点击收起/展开" @click="linkDetailExpanded = !linkDetailExpanded">
                <span class="toggle-icon">{{ linkDetailExpanded ? '▼' : '▶' }}</span>
                <span>📊 链接明细</span>
                <small>({{ linkDashboardMeta.total.toLocaleString() }}条)</small>
              </button>
              <div class="link-detail-controls">
                <input v-model="linkQuery.search" class="link-search-input" placeholder="🔍 搜索链接ID/编码/标题..." @input="schedulePromotionLinkRefresh" @keyup.enter="refreshPromotionLinkViews" />
                <input v-model="dateStart" type="date" :min="availableDates[0]" :max="availableDates.at(-1)" title="开始日期" @change="normalizeLinkDateRange" />
                <span>至</span>
                <input v-model="dateEnd" type="date" :min="availableDates[0]" :max="availableDates.at(-1)" title="结束日期" @change="normalizeLinkDateRange" />
                <span>每页</span>
                <select v-model.number="linkQuery.size" @change="refreshPromotionLinkViews"><option :value="20">20条</option><option :value="50">50条</option><option :value="100">100条</option></select>
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

        </section>

        <section v-if="activeTab === 'promotion' && promotionExpandedMode === 'data' && promotionExpandedRow" class="panel promotion-daily-summary-panel">
          <div class="panel-heading">
            <div>
              <h2>📅 每日合并数据 · {{ promotionExpandedRow.linkId }}</h2>
              <p>利润按链接 ID + 负责人 + 数据日期聚合，推广按商品 ID + 日期 + 小时先聚合后汇总到日期。</p>
            </div>
            <button type="button" class="button secondary compact" @click="closePromotionDetails">收起</button>
          </div>
          <div class="promotion-daily-table-scroll">
            <table class="promotion-hourly-table">
              <thead><tr><th>数据日期</th><th>负责人</th><th>单量</th><th>订单金额(元)</th><th>毛利(元)</th><th>利润率</th><th>推广花费(元)</th><th>推广交易额(元)</th><th>推广投产比</th><th>净成交笔数</th></tr></thead>
              <tbody>
                <tr v-for="item in (promotionExpandedRow.dailyRows || [])" :key="`${promotionExpandedRow.linkId}-${item.dataDate}-${item.person}`">
                  <td>{{ item.dataDate }}</td><td>{{ item.person || '—' }}</td><td>{{ Number(item.profitOrders || 0).toLocaleString() }}</td><td>{{ formatPromotionMoney(item.orderAmount) }}</td><td>{{ formatPromotionMoney(item.grossProfit) }}</td><td>{{ Number(item.profitRate || 0).toFixed(2) }}</td><td>{{ formatPromotionMoney(item.promotionSpend) }}</td><td>{{ formatPromotionMoney(item.promotionRevenue) }}</td><td>{{ Number(item.promotionRoi || 0).toFixed(2) }}</td><td>{{ Number(item.promotionNetOrders || 0).toLocaleString() }}</td>
                </tr>
                <tr v-if="!(promotionExpandedRow.dailyRows || []).length"><td colspan="10" class="empty-cell">当前链接在所选日期范围内暂无每日合并数据</td></tr>
              </tbody>
            </table>
          </div>
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
                  <select v-model="filter.op" class="link-filter-op" @change="normalizeLinkFilterOperator(filter)"><option v-if="linkFilterType(filter) === 'text'" value="contains">包含</option><option value="eq">=</option><option v-if="linkFilterType(filter) !== 'text'" value="between">区间</option><option v-if="linkFilterType(filter) !== 'text'" value="gte">≥</option><option v-if="linkFilterType(filter) !== 'text'" value="lte">≤</option></select>
                   <select v-if="filter.field === '品牌' || filter.field === '在售状态'" v-model="filter.v1" class="link-filter-value link-brand-value" @change="applyLinkFilters"><option value="">{{ filter.field === '在售状态' ? '选择商品状态' : '选择品牌' }}</option><option v-for="option in (filter.field === '在售状态' ? ['在售', '已下架'] : brandOptions)" :key="option" :value="option">{{ option }}</option></select>
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

        <section v-else-if="activeTab === 'cost'" class="content-grid">
          <ChartPanel title="整体成本结构" subtitle="当前范围" :options="costOption" :empty="!hasData" :height="340" />
          <ChartPanel title="负责人成本结构" subtitle="收入、成本、快递与推广费" :options="costPersonOption" :empty="!peopleRows.length" :height="340" />
          <ChartPanel title="推广费 vs 平台利润" subtitle="当前范围" :options="promoProfitOption" :empty="!peopleRows.length" :height="320" />
          <ChartPanel title="推广效率" subtitle="每 1 元推广费带来的收入" :options="promoEfficiencyOption" :empty="!peopleRows.length" :height="320" />
        </section>

        <section v-else-if="activeTab === 'admin'" class="admin-section">
          <section class="panel admin-header"><div><h2>管理中台</h2><p>集中维护链接维度的品牌、商品编码、商品名称与运营判断标准。</p></div></section>
          <section class="panel operation-queue-panel" aria-labelledby="operation-queue-title">
            <div class="panel-heading operation-queue-heading">
              <div><h2 id="operation-queue-title">⏱ 操作任务队列</h2><p>统一查看调整投产和产品下架任务；系统按发起时间串行执行，同一时间只运行一个任务。</p></div>
              <button type="button" class="button secondary compact" :disabled="operationQueueLoading" @click="loadOperationQueueNow">{{ operationQueueLoading ? '刷新中…' : '🔄 刷新队列' }}</button>
            </div>
            <div class="operation-queue-summary" aria-label="任务队列概览">
              <div><span>执行中</span><strong>{{ operationQueue.summary.running || 0 }}</strong></div>
              <div><span>排队中</span><strong>{{ operationQueue.summary.pending || 0 }}</strong></div>
              <div><span>中断中</span><strong>{{ operationQueue.summary.cancelling || 0 }}</strong></div>
              <div><span>已完成</span><strong>{{ operationQueue.summary.completed || 0 }}</strong></div>
            </div>
            <p v-if="operationQueueError" class="operation-queue-error" role="alert">{{ operationQueueError }}</p>
            <div v-if="operationQueue.tasks.length" class="operation-task-list">
              <article v-for="task in operationQueue.tasks" :key="task.id" class="operation-task-item">
                <span class="operation-task-status" :class="operationTaskStatusTone(task.status)">{{ operationTaskStatusLabel(task.status) }}</span>
                <div class="operation-task-main"><strong>{{ task.operation_label || task.operation_name }}</strong><code>{{ task.id }}</code><small>发起于 {{ task.created_at || '—' }}</small></div>
                <div class="operation-task-detail"><span>{{ Number(task.count || 0).toLocaleString() }} 条链接</span><small :title="formatOperationStores(task)">{{ formatOperationStores(task) }}</small></div>
                <div class="operation-task-position"><span>{{ operationTaskQueueHint(task) }}</span><small>{{ task.operator || '链接监控' }}</small></div>
                <div v-if="operationTaskCanCancel(task)" class="operation-task-actions">
                  <template v-if="operationInterruptConfirmId === task.id">
                    <button type="button" class="button danger compact" :disabled="operationCancellingId === task.id" @click="interruptOperationTask(task)">{{ operationCancellingId === task.id ? '处理中…' : (task.status === 'pending' ? '确认取消' : '确认中断') }}</button>
                    <button type="button" class="button secondary compact" :disabled="operationCancellingId === task.id" @click="operationInterruptConfirmId = ''">返回</button>
                  </template>
                  <button v-else type="button" class="button danger compact" @click="operationInterruptConfirmId = task.id">{{ task.status === 'pending' ? '取消排队' : '中断任务' }}</button>
                </div>
              </article>
            </div>
            <div v-else-if="!operationQueueLoading" class="operation-queue-empty">当前没有排队或执行中的任务</div>
            <details v-if="operationQueue.history.length" class="operation-history">
              <summary>最近任务记录（{{ operationQueue.history.length }}）</summary>
              <div class="operation-history-list"><div v-for="task in operationQueue.history" :key="`history-${task.id}`"><span class="operation-task-status" :class="operationTaskStatusTone(task.status)">{{ operationTaskStatusLabel(task.status) }}</span><strong>{{ task.operation_label || task.operation_name }}</strong><code>{{ task.id }}</code><small>{{ task.completed_at || task.created_at || '—' }}</small></div></div>
            </details>
            <p class="operation-queue-note">说明：取消排队会立即生效；执行中任务会先提交中断请求，由 B 电脑监听器清理尚未执行完的触发文件。</p>
          </section>
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
                              <input v-model="filter.fieldSearch" class="standard-filter-field-search" placeholder="搜索字段" aria-label="搜索字段" />
                              <select v-model="filter.field" class="link-filter-field" aria-label="选择筛选字段" @change="onStandardFilterFieldChange(row, filter); queryStandardRow(row)"><option value="">— 选择字段 —</option><option v-if="filter.fieldSearch && !standardFilterFieldOptions(filter).length" value="" disabled>没有匹配字段</option><option v-for="field in standardFilterFieldOptions(filter)" :key="field.key" :value="field.key">{{ field.label }}</option></select>
                              <select v-model="filter.op" class="link-filter-op" @change="normalizeStandardFilterOperator(row, filter); queryStandardRow(row)"><option v-if="standardFilterType(row, filter) === 'text'" value="contains">包含</option><option value="eq">=</option><option v-if="standardFilterType(row, filter) !== 'text'" value="between">区间</option><option v-if="standardFilterType(row, filter) !== 'text'" value="gte">≥</option><option v-if="standardFilterType(row, filter) !== 'text'" value="lte">≤</option></select>
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

    <div v-if="promotionTrendOpen" class="promotion-drawer-backdrop" @click="closePromotionDrawer"></div>
    <aside v-if="promotionTrendOpen" class="promotion-drawer" role="dialog" aria-modal="true" aria-labelledby="promotion-drawer-title">
      <header class="promotion-drawer-head">
        <div class="promotion-drawer-head-copy">
          <span class="promotion-drawer-kicker">DATA OVERVIEW</span>
          <h2 id="promotion-drawer-title">{{ promotionDrawerMode === 'row' ? (promotionDrawerRow?.title || promotionDrawerRow?.linkId || '链接数据总览') : promotionSelectedKpiCard.label }}</h2>
          <p v-if="promotionDrawerMode === 'row'">链接 ID：{{ promotionDrawerRow?.linkId }} · 推广字段按日期 + 小时展示，利润字段按数据日期展示</p><p v-else>当前指标的对比值、趋势与每日汇总明细</p>
        </div>
        <div class="promotion-drawer-actions">
          <strong>{{ promotionSelectedKpiCard.value }}</strong>
          <button type="button" class="modal-close" aria-label="关闭数据总览" @click="closePromotionDrawer">×</button>
        </div>
      </header>
      <div class="promotion-drawer-datebar">
        <div><span>数据范围 {{ promotionRangeHint }}</span><span>对比周期 {{ promotionDrawerComparison?.previousDate || '—' }}</span></div>
        <span>数据日期</span>
      </div>
      <div class="promotion-drawer-tabs" role="tablist" aria-label="指标详情视图">
        <button type="button" class="promotion-drawer-tab" :class="{ active: promotionDrawerTab === 'trend' }" role="tab" :aria-selected="promotionDrawerTab === 'trend'" @click="promotionDrawerTab = 'trend'">↗ 趋势图</button>
        <button type="button" class="promotion-drawer-tab" :class="{ active: promotionDrawerTab === 'table' }" role="tab" :aria-selected="promotionDrawerTab === 'table'" @click="promotionDrawerTab = 'table'">▦ 表格</button>
      </div>
      <div class="promotion-drawer-body">
        <div class="promotion-drawer-kpi-grid">
          <button v-for="card in orderedPromotionCards(activePromotionDrawerCards)" :key="card.key" type="button" class="promotion-drawer-kpi" :class="{ active: card.key === promotionSelectedKpi, 'is-dragging': promotionCardDragKey === card.key }" :title="`拖动调整${card.label}卡片顺序`" @click="handlePromotionCardClick($event, card.key)" @pointerdown="startPromotionCardPointerDrag($event, card.key)" @pointerenter="handlePromotionCardPointerEnter(card.key)" @pointermove="handlePromotionCardPointerEnter(card.key)" @mouseenter="handlePromotionCardPointerEnter(card.key)" @pointerup="endPromotionCardPointerDrag" @pointercancel="endPromotionCardPointerDrag">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <small :class="card.previousTone">对比值 {{ card.previousValue }}</small>
          </button>
        </div>
        <template v-if="promotionDrawerTab === 'trend'">
           <div class="promotion-drawer-chart-head"><div><strong>{{ promotionSelectedKpiCard.label }}走势</strong><span>{{ promotionDrawerGranularityHint }} · {{ promotionRangeHint }}</span><small v-if="promotionDrawerHourlyLoading" class="promotion-drawer-hourly-status">正在读取推广日数据…</small><small v-else-if="promotionDrawerHourlyError" class="promotion-drawer-hourly-status error">{{ promotionDrawerHourlyError }}</small></div><b>{{ promotionSelectedKpiCard.value }}</b></div>
           <div v-if="promotionDrawerHourlyRows.length" class="promotion-hourly-chart">
             <svg viewBox="0 0 920 270" role="img" :aria-label="`${promotionSelectedKpiCard.label}当前周期与对比周期趋势图`" preserveAspectRatio="none" @pointermove="handlePromotionTrendPointerMove" @mouseleave="hidePromotionTrendTooltip">
               <line v-for="line in promotionTrendGridLines" :key="line.y" x1="0" :y1="line.y + 28" x2="920" :y2="line.y + 28" class="promotion-trend-grid-line" />
               <line v-if="promotionHoveredTrendPoint" :x1="promotionHoveredTrendPoint.x" y1="28" :x2="promotionHoveredTrendPoint.x" y2="238" class="promotion-trend-hover-guide" />
               <polyline :points="promotionDrawerHourlyPoints" class="promotion-trend-line" />
               <polyline v-if="promotionDrawerPreviousHourlyPoints" :points="promotionDrawerPreviousHourlyPoints" class="promotion-trend-compare-line" />
               <circle v-for="(point, index) in promotionDrawerHourlyPointsList" :key="point.key" :cx="point.x" :cy="point.y" r="4" class="promotion-trend-point" tabindex="0" @mouseenter="showPromotionTrendTooltip(point, 'current', index)" @focus="showPromotionTrendTooltip(point, 'current', index)" @blur="hidePromotionTrendTooltip"><title>{{ point.tooltip }}</title></circle>
               <circle v-for="(point, index) in promotionDrawerPreviousHourlyPointsList" :key="point.key" :cx="point.x" :cy="point.y" r="4" class="promotion-trend-compare-point" tabindex="0" @mouseenter="showPromotionTrendTooltip(point, 'comparison', index)" @focus="showPromotionTrendTooltip(point, 'comparison', index)" @blur="hidePromotionTrendTooltip"><title>{{ point.tooltip }}</title></circle>
             </svg>
             <div v-if="promotionHoveredTrendPoint" class="promotion-trend-tooltip" :style="promotionTrendTooltipStyle" role="status" aria-live="polite">
               <strong>{{ promotionHoveredTrendPoint.seriesLabel }}</strong>
               <div><span>数据日期</span><b>{{ promotionHoveredTrendPoint.date }}</b></div>
               <div><span>{{ promotionSelectedKpiCard.label }}</span><b>{{ promotionHoveredTrendPoint.display }}</b></div>
               <div v-if="promotionHoveredTrendPoint.compareDate" class="promotion-trend-tooltip-compare"><span>{{ promotionHoveredTrendPoint.compareSeriesLabel }} {{ promotionHoveredTrendPoint.compareDate }}</span><b>{{ promotionHoveredTrendPoint.compareDisplay }}</b></div>
             </div>
               <div class="promotion-trend-legend"><span class="promotion-trend-legend-current"><i></i>当前周期 {{ promotionRangeHint }}</span><span class="promotion-trend-legend-compare"><i></i>对比周期 {{ promotionComparisonRange.label || '—' }}</span></div>
               <div class="promotion-trend-axis"><span>{{ promotionDrawerHourlyRows[0].hourLabel }}</span><span>{{ promotionDrawerHourlyRows[Math.min(12, promotionDrawerHourlyRows.length - 1)].hourLabel }}</span><span>{{ promotionDrawerHourlyRows.at(-1).hourLabel }}</span></div>
          </div>
          <div v-else class="promotion-trend-empty">当前筛选范围暂无可展示的趋势数据</div>
        </template>
        <template v-else>
          <div class="promotion-drawer-table-scroll">
            <table class="promotion-drawer-table"><thead><tr><th>{{ promotionDrawerTimeColumnLabel }}</th><th>{{ promotionSelectedKpiCard.label }}</th><th>变化幅度</th><th>{{ promotionDrawerComparisonColumnLabel }}</th></tr></thead><tbody><tr v-for="(item, index) in promotionDrawerHourlyRows" :key="item.key"><td>{{ item.hourLabel }}</td><td>{{ item.display }}</td><td :class="item.changeTone">{{ item.change }}</td><td>{{ promotionDrawerComparisonDate(item, index) }}</td></tr></tbody></table>
          </div>
        </template>
      </div>
    </aside>

    <div v-if="adjustModalOpen" class="modal-backdrop" @click.self="closePromotionAdjust">
      <section class="promotion-adjust-modal panel" role="dialog" aria-modal="true" aria-labelledby="promotion-adjust-title">
        <div class="modal-header">
          <div><h2 id="promotion-adjust-title">📊 调整投产</h2><p>已选择 {{ promotionAdjustOperationIds.length }} 条链接，请确认调整范围</p></div>
          <button type="button" class="modal-close" aria-label="关闭弹窗" :disabled="adjustingPromotion" @click="closePromotionAdjust">×</button>
        </div>
        <div class="adjust-selection-list">
          <div v-for="item in selectedAdjustLinkRows" :key="item.linkId" class="adjust-selection-item"><code>{{ item.linkId }}</code><span>{{ item.storeName || '未识别店铺' }}</span></div>
        </div>
         <div class="adjust-form">
           <fieldset class="adjust-preset-fieldset"><legend>选择调整档次</legend><div class="adjust-preset-grid" role="radiogroup" aria-label="投产调整档次"><label v-for="preset in promotionAdjustPresets" :key="preset.key" class="adjust-preset" :class="{ 'is-selected': adjustPreset === preset.value }"><input v-model="adjustPreset" type="radio" name="promotion-adjust-preset" :value="preset.value" /><span class="adjust-preset-copy"><strong>{{ preset.label }}</strong><small>{{ preset.display }}</small></span></label></div></fieldset>
           <p class="adjust-preset-hint">提交后将按选中的档次上调投产比。</p>
         </div>
        <fieldset class="operation-schedule-fieldset"><legend>执行方式</legend><div class="operation-schedule-options" role="radiogroup" aria-label="调整投产执行方式"><label><input v-model="adjustScheduleMode" type="radio" name="promotion-adjust-schedule-mode" value="immediate" /> 立即执行</label><label><input v-model="adjustScheduleMode" type="radio" name="promotion-adjust-schedule-mode" value="scheduled" /> 定时执行</label></div><label v-if="adjustScheduleMode === 'scheduled'" class="operation-schedule-input">执行时间 <input v-model="adjustScheduledAt" type="datetime-local" :min="minimumScheduleDateTime" /></label><small>定时任务会先进入队列，到达指定时间后由 B 电脑监听器触发原有影刀流程。</small></fieldset>
        <p v-if="adjustMessage" class="adjust-message">{{ adjustMessage }}</p>
        <div class="modal-actions"><button type="button" class="button secondary" :disabled="adjustingPromotion" @click="closePromotionAdjust">取消</button><button type="button" class="button primary" :disabled="adjustingPromotion" @click="submitPromotionAdjust">{{ adjustingPromotion ? '提交中…' : (adjustScheduleMode === 'scheduled' ? '确认定时' : '立即提交') }}</button></div>
      </section>
    </div>
    <div v-if="delistConfirmOpen" class="modal-backdrop" @click.self="closeDelistConfirm">
      <section class="promotion-adjust-modal panel delist-confirm-modal" role="dialog" aria-modal="true" aria-labelledby="delist-confirm-title">
        <div class="modal-header">
          <div><h2 id="delist-confirm-title">📦 确认产品下架</h2><p>以下 {{ delistOperationIds.length }} 条链接将提交产品下架任务，请确认。</p></div>
          <button type="button" class="modal-close" aria-label="关闭下架确认弹窗" :disabled="delisting" @click="closeDelistConfirm">×</button>
        </div>
        <div class="delist-confirm-warning">请核对店铺名称和链接 ID。确认后将提交下架任务，请在拼多多推广后台确认最终执行结果。</div>
        <div class="delist-selection-list" role="list" aria-label="待下架链接">
          <div v-for="item in selectedDelistLinkRows" :key="item.linkId" class="delist-selection-item" role="listitem">
            <div><span>店铺名称</span><strong>{{ item.storeName || '未识别店铺' }}</strong></div>
            <div><span>链接 ID</span><code>{{ item.linkId }}</code></div>
          </div>
        </div>
        <fieldset class="operation-schedule-fieldset"><legend>执行方式</legend><div class="operation-schedule-options" role="radiogroup" aria-label="产品下架执行方式"><label><input v-model="delistScheduleMode" type="radio" name="delist-schedule-mode" value="immediate" /> 立即执行</label><label><input v-model="delistScheduleMode" type="radio" name="delist-schedule-mode" value="scheduled" /> 定时执行</label></div><label v-if="delistScheduleMode === 'scheduled'" class="operation-schedule-input">执行时间 <input v-model="delistScheduledAt" type="datetime-local" :min="minimumScheduleDateTime" /></label><small>定时任务会先进入队列，到达指定时间后由 B 电脑监听器触发原有影刀流程。</small></fieldset>
        <p v-if="delistMessage" class="adjust-message">{{ delistMessage }}</p>
        <div class="modal-actions"><button type="button" class="button secondary" :disabled="delisting" @click="closeDelistConfirm">取消</button><button type="button" class="button danger" :disabled="delisting" @click="submitSelectedLinks">{{ delisting ? '提交中…' : (delistScheduleMode === 'scheduled' ? '确认定时' : '确认下架') }}</button></div>
      </section>
    </div>
    <div v-if="promotionHelpOpen || promotionReportOpen" class="modal-backdrop" @click.self="promotionHelpOpen = promotionReportOpen = false">
      <section class="promotion-info-modal panel" role="dialog" aria-modal="true">
        <div class="modal-header"><div><h2>{{ promotionHelpOpen ? '商品推广说明' : '推广数据口径' }}</h2><p>{{ promotionHelpOpen ? '商品推广页的前端交互入口已按推广平台结构预留。' : '推广数据来自“商品_分天数据”工作表，按店铺、商品 ID、数据日期汇总。' }}</p></div><button type="button" class="modal-close" aria-label="关闭" @click="promotionHelpOpen = promotionReportOpen = false">×</button></div>
        <div v-if="promotionHelpOpen" class="promotion-info-list"><p>• 时间范围使用“数据日期”，支持今日、昨日、近 7 日、近 30 日和近 90 日。</p><p>• 搜索支持推广名称、商品名称、商品 ID，多个 ID 可用逗号或空格分隔。</p><p>• 商品行的“详情 / 数据 / 更多”分别对应基础信息、每日推广数据和运营动作入口。</p></div>
        <div v-else class="promotion-info-list"><p>• 当前商品推广列表复用看板已有商品/链接数据生成前端演示行。</p><p>• 未来接入推广数据表时，建议使用“数据日期 + 小时 + 商品 ID”作为明细粒度。</p><p>• 花费、交易额、投产比等字段保留独立口径，避免与利润表聚合结果混用。</p></div>
      </section>
    </div>
    <div v-if="promotionImagePreviewUrl" class="promotion-image-preview-backdrop" @click.self="closePromotionImagePreview">
      <section class="promotion-image-preview-dialog" role="dialog" aria-modal="true" aria-labelledby="promotion-image-preview-title">
        <h2 id="promotion-image-preview-title" class="sr-only">链接主图预览</h2>
        <button type="button" class="promotion-image-preview-close" aria-label="关闭图片预览" @click="closePromotionImagePreview">×</button>
        <div class="promotion-image-preview-stage"><img :src="promotionImagePreviewUrl" alt="链接主图大图预览" /></div>
      </section>
    </div>
    <div v-if="promotionNoticeMessage" class="promotion-toast" role="status">{{ promotionNoticeMessage }}</div>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import ChartPanel from './components/ChartPanel.vue';
import { useProfitData } from './composables/useProfitData';

const navItems = [
  { key: 'promotion', label: '商品推广', icon: '◉' },
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

const { data, status, targets, standards, loading, error, lastUpdated, links, linksMeta, linksLoading, linkFields: linkFieldsRef, linkDashboard, linkDashboardLoading, linkSummary, linkSummaryLoading, availableDates, loadAll, loadPromotionSummary, loadLinkOperatingSummary, loadPromotionHourly, refresh, queryLinks, loadLinks, loadLinkDashboard, loadLinkSummary, saveTargets, saveStandard, deleteStandard, submitDelist, submitPromotionAdjust: sendPromotionAdjust, loadOperationQueue: fetchOperationQueue, cancelOperationTask } = useProfitData();
// 字段接口首次加载或热更新期间可能暂时没有返回 ref；当前数据库字段仍由 linkFieldOrder 提供完整兜底。
const linkFields = linkFieldsRef || ref([]);
const activeTab = ref('promotion');
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
const operationQueue = ref({ tasks: [], history: [], summary: { pending: 0, running: 0, cancelling: 0, completed: 0, failed: 0, cancelled: 0 } });
const operationQueueLoading = ref(false);
const operationQueueError = ref('');
const operationCancellingId = ref('');
const operationInterruptConfirmId = ref('');
let operationQueueTimer = null;
const showPersonLines = ref(false);
const focusedProfitRateSeries = ref(null);
const focusedProductProfitSeries = ref(null);
const targetForm = reactive({ monthTarget: 0, profitRate: 0, persons: {}, brands: {} });
const savingTargets = ref(false);
const targetMessage = ref('');
const selectedLinks = ref([]);
const adjustModalOpen = ref(false);
const adjustingPromotion = ref(false);
const promotionAdjustTargetIds = ref([]);
const adjustScheduleMode = ref('immediate');
const adjustScheduledAt = ref('');
const delistConfirmOpen = ref(false);
const delisting = ref(false);
const delistMessage = ref('');
const delistTargetIds = ref([]);
const delistScheduleMode = ref('immediate');
const delistScheduledAt = ref('');
 const promotionAdjustPresets = Object.freeze([
   { key: 'maintenance-005', label: '日常维护', display: '+0.05', value: 0.05 },
   { key: 'serious-loss-01', label: '亏损严重', display: '+0.1', value: 0.1 },
   { key: 'serious-loss-02', label: '亏损严重', display: '+0.2', value: 0.2 },
   { key: 'maintenance-001', label: '日常维护', display: '+0.01', value: 0.01 },
 ]);
const adjustPreset = ref(0.05);
const adjustMessage = ref('');
const minimumScheduleDateTime = computed(() => {
  const now = new Date();
  now.setSeconds(0, 0);
  const pad = (value) => String(value).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
});
const promotionDatePresets = Object.freeze([{ key: 'today', label: '今日' }, { key: 'yesterday', label: '昨日' }, { key: '7d', label: '近 7 日' }, { key: '30d', label: '近 30 日' }, { key: '90d', label: '近 90 日' }]);
const promotionDatePreset = ref('30d');
const promotionFilters = reactive({ start: '', end: '', search: '', status: '', bidType: '', stage: '', brand: '' });
const promotionLoading = ref(false);
const promotionRows = ref([]);
// 链接经营接口返回的是当前筛选范围的全量汇总，卡片不能只依赖页面行重新累加。
const promotionApiSummary = ref({});
const promotionPage = ref(1);
const promotionPageSize = ref(10);
const promotionColumnsOpen = ref(false);
const promotionVisibleColumns = ref(['storeName', 'imageUrl', 'title', 'linkId', 'productCode', 'createdAt', 'person', 'orderAmount', 'grossProfit', 'grossMargin', 'platformProfit', 'profitRate', 'promotionSpend', 'promotionRevenue', 'promotionRoi', 'promotionNetOrders', 'impressions', 'clicks']);
const defaultPromotionVisibleColumns = Object.freeze([...promotionVisibleColumns.value]);
const promotionColumnDraft = ref([...promotionVisibleColumns.value]);
const promotionColumnSearch = ref('');
const promotionDraggedColumn = ref('');
const promotionDimension = ref('link');
const promotionDimensions = Object.freeze([
  { key: 'brand', label: '品牌' },
  { key: 'person', label: '负责人' },
  { key: 'store', label: '店铺' },
  { key: 'product', label: '商品' },
  { key: 'link', label: '链接' },
]);
const promotionSort = reactive({ key: 'promotionRevenue', order: 'desc' });
const selectedPromotionIds = ref([]);
const selectedOperationIds = computed(() => selectedPromotionIds.value.length ? selectedPromotionIds.value : selectedLinks.value);
const promotionExpandedKey = ref('');
const promotionExpandedMode = ref('detail');
const promotionHelpOpen = ref(false);
const promotionReportOpen = ref(false);
const promotionImagePreviewUrl = ref('');
const promotionNoticeMessage = ref('');
const promotionMoreFiltersOpen = ref(false);
const promotionDataSummaryOpen = ref(false);
const promotionHourPreset = ref('all');
const promotionHourDate = ref('all');
const promotionHourlySourceRows = ref([]);
const promotionHourlyLoading = ref(false);
const promotionHourlyError = ref('');
// 抽屉趋势单独维护小时源数据，避免与表格内“数据”展开区域互相覆盖。
const promotionDrawerHourlySourceRows = ref([]);
const promotionDrawerPreviousHourlySourceRows = ref([]);
const promotionDrawerHourlyLoading = ref(false);
const promotionDrawerHourlyError = ref('');
const promotionDrawerHourlyLoaded = ref(false);
const promotionDrawerHourlyRequestKey = ref('');
const promotionNoticeTimer = ref(null);
const promotionSelectedKpi = ref('spend');
const promotionTrendOpen = ref(false);
const promotionDrawerTab = ref('trend');
const promotionDrawerMode = ref('kpi');
const promotionDrawerRow = ref(null);
const promotionComparisonRows = ref([]);
const promotionComparisonLoading = ref(false);
const promotionComparisonError = ref('');
const promotionComparisonRequestKey = ref('');
const promotionKpiTrack = ref(null);
const promotionCardOrderStorageKey = 'link-monitor-promotion-card-order';
const promotionCardOrder = ref(loadPromotionCardOrder());
const promotionCardDragKey = ref('');
const promotionCardPointerMoved = ref(false);
const promotionCardSuppressClick = ref(false);
const linkQuery = reactive({ search: '', store_person: '', profit_rate_lte: '', size: 20 });
const linkSummaryQuery = reactive({ search: '', size: 20 });
const linkSummarySort = reactive({ key: 'revenue', order: 'desc' });
const activeLinkPresetId = ref('');
const activeLinkPresetFilters = ref([]);
const expandedLinkSummaryId = ref('');
const linkSummaryDailyRows = ref([]);
const linkSummaryDailyLoading = ref(false);
const linkSummaryDailyError = ref('');
const brandOptions = Object.freeze(['浪奇', '威王', '舒蕾', '白牌']);
const globalFilters = reactive({ link_ids: '', product_code: '', product_name: '', orders: '', brand: '', store_name: '', store_person: '', sale_status: '' });
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
  '链接id', '链接创建时间', '在售状态', '商品编码', '商品标题', '店铺名称', '品牌', '负责人', '数据日期', '单量', '收入', '成本', '成本占比', '快递', '快递占比', '成本+快递', '货品快递总和占比', '毛利', '毛利率', '技术服务费', '预估售后', '推广费', '推广费占比', '平台利润', '利润率', '运费险', '税费', '来源文件',
  '出价方式', '商品名称', 'store', '推广来源文件', '总花费(元)', '交易额(元)', '净交易额(元)', '净成交笔数', '成交笔数', '直接交易额(元)', '间接交易额(元)', '直接成交笔数', '间接成交笔数', '曝光量', '点击量', '询单花费(元)', '询单量', '收藏花费(元)', '收藏量', '关注花费(元)', '关注量', '平均收藏成本(元)', '平均关注成本(元)', '平均询单成本(元)', '全站推广费比', '净交易额占比', '实际投产比', '净实际投产比', '每笔净成交花费(元)', '每笔成交花费(元)', '每笔成交金额(元)', '每笔直接成交金额(元)', '每笔间接成交金额(元)', '推广数据匹配',
];
const linkPercentFields = new Set(['成本占比', '快递占比', '货品快递总和占比', '毛利率', '推广费占比', '利润率', '全站推广费比', '净交易额占比']);
const linkFieldLabels = Object.freeze({ 链接id: '链接 ID', 链接创建时间: '链接创建时间', 在售状态: '商品状态', 店铺名称: '店铺', 数据日期: '日期', 推广费占比: '推广占比', 推广数据匹配: '推广数据匹配' });
const linkColumnOptions = computed(() => {
  const apiFields = linkFields.value || [];
  const apiMap = new Map(apiFields.map((field) => [field.key, field]));
  const keys = apiFields.length ? linkFieldOrder.filter((key) => key === '品牌' || key === '在售状态' || apiMap.has(key)) : linkFieldOrder;
  const extras = apiFields.map((field) => field.key).filter((key) => key !== 'id' && !keys.includes(key));
  return [...keys, ...extras].map((key) => {
    const apiField = apiMap.get(key);
    return { key, label: linkFieldLabels[key] || apiField?.label || key, type: key === '品牌' ? 'text' : (apiField?.type || (linkPercentFields.has(key) ? 'number' : 'text')) };
  });
});
const linkFilterFields = computed(() => linkColumnOptions.value);
const linkFilterPresets = computed(() => standardRows.value
  .filter((row) => row.id !== undefined && row.id !== null && row.enabled && standardActiveFilters(row).length)
  .map((row) => ({
    id: String(row.id),
    label: row.note?.trim() || `${row.dimensionType === 'brand' ? '品牌' : row.dimensionType === 'person' ? '负责人' : '链接'}筛选 ${row.id}`,
    summary: standardFilterSummary(row),
    filters: standardActiveFilters(row),
  })));
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

const promotionColumns = Object.freeze([
  { key: 'storeName', label: '店铺名称' },
  { key: 'imageUrl', label: '链接主图', tone: 'promotion-image-cell', sortable: false },
  { key: 'title', label: '链接标题', tone: 'promotion-title-cell' },
  { key: 'linkId', label: '链接 ID', tone: 'promotion-id-cell' },
  { key: 'productCode', label: '商品编码' },
  { key: 'createdAt', label: '链接创建时间' },
  { key: 'saleStatus', label: '商品状态' },
  { key: 'person', label: '负责人' },
  { key: 'profitOrders', label: '利润单量', tone: 'number' },
  { key: 'orderAmount', label: '订单金额(元)', tone: 'number' },
  { key: 'refundAmount', label: '退款金额(元)', tone: 'number' },
  { key: 'goodsCost', label: '货品成本(元)', tone: 'number' },
  { key: 'shippingCost', label: '快递成本(元)', tone: 'number' },
  { key: 'afterRefundOrderAmount', label: '扣除退款订单金额(元)', tone: 'number' },
  { key: 'afterReturnOrderAmount', label: '扣除退货率后订单金额(元)', tone: 'number' },
  { key: 'afterReturnGoodsCost', label: '扣除退货率后货品成本(元)', tone: 'number' },
  { key: 'costPct', label: '成本占比', tone: 'rate' },
  { key: 'afterReturnShippingCost', label: '扣除退货率后快递成本(元)', tone: 'number' },
  { key: 'goodsShippingTotal', label: '货品快递总和(元)', tone: 'number' },
  { key: 'goodsShippingPct', label: '货品快递总和占比', tone: 'rate' },
  { key: 'remoteSurcharge', label: '偏远加收(元)', tone: 'number' },
  { key: 'grossProfit', label: '毛利(元)', tone: 'number' },
  { key: 'grossMargin', label: '毛利率', tone: 'rate' },
  { key: 'platformProfit', label: '平台利润(元)', tone: 'number' },
  { key: 'profitRate', label: '利润率', tone: 'rate' },
  { key: 'promotionSpend', label: '成交花费(元)', tone: 'number' },
  { key: 'promotionTotalSpend', label: '总花费(元)', tone: 'number' },
  { key: 'promotionRevenue', label: '推广交易额(元)', tone: 'number' },
  { key: 'promotionRoi', label: '实际投产比', tone: 'rate' },
  { key: 'promotionNetRoi', label: '净实际投产比', tone: 'rate' },
  { key: 'promotionNetRevenue', label: '净交易额(元)', tone: 'number' },
  { key: 'promotionNetOrders', label: '净成交笔数', tone: 'number' },
  { key: 'promotionAvgNetOrderSpend', label: '每笔净成交花费(元)', tone: 'number' },
  { key: 'promotionNetRevenueRatio', label: '净交易额占比', tone: 'rate' },
  { key: 'promotionNetOrdersRatio', label: '净成交笔数占比', tone: 'rate' },
  { key: 'promotionAvgNetOrderRevenue', label: '每笔净成交金额(元)', tone: 'number' },
  { key: 'settledRevenue', label: '结算交易额(元)', tone: 'number' },
  { key: 'settledRoi', label: '结算投产比', tone: 'rate' },
  { key: 'settledOrders', label: '结算成交笔数', tone: 'number' },
  { key: 'refundExemptionRate', label: '退款豁免率', tone: 'rate' },
  { key: 'cancelExemptionRate', label: '退单豁免率', tone: 'rate' },
  { key: 'settledAvgOrderSpend', label: '每笔结算成交花费(元)', tone: 'number' },
  { key: 'revenueSettlementRate', label: '交易额结算率', tone: 'rate' },
  { key: 'orderSettlementRate', label: '订单结算率', tone: 'rate' },
  { key: 'settledAvgOrderRevenue', label: '每笔结算成交金额(元)', tone: 'number' },
  { key: 'promotionOrders', label: '成交笔数', tone: 'number' },
  { key: 'promotionAvgOrderSpend', label: '每笔成交花费(元)', tone: 'number' },
  { key: 'promotionAvgOrderRevenue', label: '每笔成交金额(元)', tone: 'number' },
  { key: 'directRevenue', label: '直接交易额(元)', tone: 'number' },
  { key: 'indirectRevenue', label: '间接交易额(元)', tone: 'number' },
  { key: 'directOrders', label: '直接成交笔数', tone: 'number' },
  { key: 'indirectOrders', label: '间接成交笔数', tone: 'number' },
  { key: 'impressions', label: '曝光量', tone: 'number' },
  { key: 'clicks', label: '点击量', tone: 'number' },
  { key: 'sitePromotionRatio', label: '全站推广费比', tone: 'rate' },
  { key: 'dataDays', label: '数据天数', tone: 'number' },
]);
const promotionColumnGroupDefinitions = Object.freeze([
  { key: 'link', label: '链接信息', keys: ['storeName', 'imageUrl', 'title', 'linkId', 'productCode', 'createdAt', 'saleStatus', 'person'] },
  { key: 'profit', label: '利润数据', keys: ['profitOrders', 'orderAmount', 'refundAmount', 'goodsCost', 'shippingCost', 'afterRefundOrderAmount', 'afterReturnOrderAmount', 'afterReturnGoodsCost', 'costPct', 'afterReturnShippingCost', 'goodsShippingTotal', 'goodsShippingPct', 'remoteSurcharge', 'grossProfit', 'grossMargin', 'platformProfit', 'profitRate'] },
  { key: 'promotion', label: '推广数据', keys: ['promotionSpend', 'promotionTotalSpend', 'promotionRevenue', 'promotionRoi', 'promotionNetRoi', 'promotionNetRevenue', 'promotionNetOrders', 'promotionAvgNetOrderSpend', 'promotionNetRevenueRatio', 'promotionNetOrdersRatio', 'promotionAvgNetOrderRevenue', 'settledRevenue', 'settledRoi', 'settledOrders', 'refundExemptionRate', 'cancelExemptionRate', 'settledAvgOrderSpend', 'revenueSettlementRate', 'orderSettlementRate', 'settledAvgOrderRevenue', 'promotionOrders', 'promotionAvgOrderSpend', 'promotionAvgOrderRevenue', 'directRevenue', 'indirectRevenue', 'directOrders', 'indirectOrders'] },
  { key: 'traffic', label: '流量数据', keys: ['impressions', 'clicks', 'sitePromotionRatio', 'dataDays'] },
]);
const promotionColumnGroups = computed(() => {
  const search = promotionColumnSearch.value.trim().toLocaleLowerCase('zh-CN');
  return promotionColumnGroupDefinitions.map((group) => ({
    ...group,
    columns: group.keys.map((key) => promotionColumns.find((column) => column.key === key)).filter(Boolean).filter((column) => !search || column.label.toLocaleLowerCase('zh-CN').includes(search)),
  })).filter((group) => group.columns.length);
});
const promotionDraftColumns = computed(() => promotionColumnDraft.value.map((key) => promotionColumns.find((column) => column.key === key)).filter(Boolean));
const visiblePromotionColumns = computed(() => promotionVisibleColumns.value
  .map((key) => promotionColumns.find((column) => column.key === key))
  .filter(Boolean));
const promotionDimensionLabel = computed(() => promotionDimensions.find((item) => item.key === promotionDimension.value)?.label || '链接');
const promotionAggregateNumberKeys = Object.freeze([...new Set([
  ...promotionColumns.filter((column) => column.tone === 'number').map((column) => column.key),
  'techServiceFee', 'estimatedAfterSale', 'profitPromotionFee', 'freightInsurance', 'tax', 'profitOrders',
])]);
function promotionDimensionValue(row) {
  if (promotionDimension.value === 'brand') return row.brand || '未分类';
  if (promotionDimension.value === 'person') return row.person || '未分配';
  if (promotionDimension.value === 'store') return row.storeName || '未命名店铺';
  if (promotionDimension.value === 'product') return row.productCode || row.title || '未命名商品';
  return row.linkId || '未命名链接';
}
function promotionAggregateDailyRows(rows) {
  const dailyMap = new Map();
  for (const source of rows) {
    for (const item of source.dailyRows || []) {
      const date = String(item.dataDate || '').slice(0, 10);
      if (!date) continue;
      const current = dailyMap.get(date) || { linkId: '', dataDate: date, person: '', _persons: new Set() };
      if (item.person) current._persons.add(item.person);
      for (const key of promotionAggregateNumberKeys) current[key] = Number(current[key] || 0) + Number(item[key] || 0);
      dailyMap.set(date, current);
    }
  }
  return [...dailyMap.values()].sort((left, right) => left.dataDate.localeCompare(right.dataDate)).map((item) => {
    const daily = { ...item, person: [...item._persons].sort().join('、') };
    delete daily._persons;
    const revenue = Number(daily.orderAmount || 0);
    daily.costPct = ratio(daily.goodsCost, revenue);
    daily.shippingPct = ratio(daily.shippingCost, revenue);
    daily.goodsShippingPct = ratio(daily.goodsShippingTotal, revenue);
    daily.grossMargin = ratio(daily.grossProfit, revenue);
    daily.profitPromotionPct = ratio(daily.profitPromotionFee, revenue);
    daily.profitRate = ratio(daily.platformProfit, revenue);
    daily.promotionRoi = daily.promotionSpend ? daily.promotionRevenue / daily.promotionSpend : 0;
    daily.promotionNetRoi = daily.promotionSpend ? daily.promotionNetRevenue / daily.promotionSpend : 0;
    daily.promotionAvgNetOrderSpend = daily.promotionNetOrders ? daily.promotionSpend / daily.promotionNetOrders : 0;
    daily.promotionNetRevenueRatio = ratio(daily.promotionNetRevenue, daily.promotionRevenue);
    daily.promotionNetOrdersRatio = ratio(daily.promotionNetOrders, daily.promotionOrders);
    daily.promotionAvgNetOrderRevenue = daily.promotionNetOrders ? daily.promotionNetRevenue / daily.promotionNetOrders : 0;
    daily.settledRoi = daily.promotionSpend ? daily.settledRevenue / daily.promotionSpend : 0;
    daily.settledAvgOrderSpend = daily.settledOrders ? daily.promotionSpend / daily.settledOrders : 0;
    daily.revenueSettlementRate = ratio(daily.settledRevenue, daily.promotionRevenue);
    daily.orderSettlementRate = ratio(daily.settledOrders, daily.promotionOrders);
    daily.settledAvgOrderRevenue = daily.settledOrders ? daily.settledRevenue / daily.settledOrders : 0;
    daily.promotionAvgOrderSpend = daily.promotionOrders ? daily.promotionSpend / daily.promotionOrders : 0;
    daily.promotionAvgOrderRevenue = daily.promotionOrders ? daily.promotionRevenue / daily.promotionOrders : 0;
    return daily;
  });
}
function promotionAggregateRow(rows, dimensionValue) {
  const first = rows[0] || {};
  const dailyRows = promotionAggregateDailyRows(rows);
  const row = {
    ...first,
    linkId: `${promotionDimension.value}:${dimensionValue}`,
    dimensionValue,
    sourceLinkIds: rows.map((item) => item.linkId).filter(Boolean),
    title: promotionDimension.value === 'link' || promotionDimension.value === 'product' ? first.title : dimensionValue,
    storeName: promotionDimension.value === 'store' ? dimensionValue : (promotionDimension.value === 'brand' ? dimensionValue : first.storeName),
    productCode: promotionDimension.value === 'product' ? dimensionValue : '—',
    person: promotionDimension.value === 'person' ? dimensionValue : (rows.length === 1 ? first.person : '多个负责人'),
    brand: promotionDimension.value === 'brand' ? dimensionValue : first.brand,
    imageUrl: first.imageUrl || '',
    createdAt: promotionDimension.value === 'link' ? first.createdAt : '',
    dailyRows,
    dataDays: dailyRows.length,
    profitDataDays: rows.reduce((sum, item) => sum + Number(item.profitDataDays || 0), 0),
    promotionDataDays: rows.reduce((sum, item) => sum + Number(item.promotionDataDays || 0), 0),
  };
  for (const key of promotionAggregateNumberKeys) row[key] = rows.reduce((sum, item) => sum + Number(item[key] || 0), 0);
  const revenue = Number(row.orderAmount || 0);
  row.costPct = ratio(row.goodsCost, revenue);
  row.shippingPct = ratio(row.shippingCost, revenue);
  row.goodsShippingPct = ratio(row.goodsShippingTotal, revenue);
  row.grossMargin = ratio(row.grossProfit, revenue);
  row.profitPromotionPct = ratio(row.profitPromotionFee, revenue);
  row.profitRate = ratio(row.platformProfit, revenue);
  row.promotionRoi = row.promotionSpend ? row.promotionRevenue / row.promotionSpend : 0;
  row.promotionNetRoi = row.promotionSpend ? row.promotionNetRevenue / row.promotionSpend : 0;
  row.promotionAvgNetOrderSpend = row.promotionNetOrders ? row.promotionSpend / row.promotionNetOrders : 0;
  row.promotionNetRevenueRatio = ratio(row.promotionNetRevenue, row.promotionRevenue);
  row.promotionNetOrdersRatio = ratio(row.promotionNetOrders, row.promotionOrders);
  row.promotionAvgNetOrderRevenue = row.promotionNetOrders ? row.promotionNetRevenue / row.promotionNetOrders : 0;
  row.settledRoi = row.promotionSpend ? row.settledRevenue / row.promotionSpend : 0;
  row.settledAvgOrderSpend = row.settledOrders ? row.promotionSpend / row.settledOrders : 0;
  row.revenueSettlementRate = ratio(row.settledRevenue, row.promotionRevenue);
  row.orderSettlementRate = ratio(row.settledOrders, row.promotionOrders);
  row.settledAvgOrderRevenue = row.settledOrders ? row.settledRevenue / row.settledOrders : 0;
  row.promotionAvgOrderSpend = row.promotionOrders ? row.promotionSpend / row.promotionOrders : 0;
  row.promotionAvgOrderRevenue = row.promotionOrders ? row.promotionRevenue / row.promotionOrders : 0;
  row.spend = row.promotionSpend || 0;
  row.revenue = row.promotionRevenue || 0;
  row.netRevenue = row.promotionNetRevenue || 0;
  row.orders = row.promotionNetOrders || 0;
  row.roi = row.promotionRoi || 0;
  row.netRoi = row.promotionNetRoi || 0;
  row.status = row.promotionDataDays ? '有推广数据' : '无推广数据';
  row.firstDate = dailyRows[0]?.dataDate || '';
  row.lastDate = dailyRows.at(-1)?.dataDate || '';
  return row;
}
const promotionDimensionRows = computed(() => {
  if (promotionDimension.value === 'link') return promotionRows.value;
  const groups = new Map();
  for (const row of promotionRows.value) {
    const value = promotionDimensionValue(row);
    const current = groups.get(value) || [];
    current.push(row);
    groups.set(value, current);
  }
  return [...groups.entries()].map(([value, rows]) => promotionAggregateRow(rows, value));
});
const sortedPromotionRows = computed(() => {
  const column = promotionColumns.find((item) => item.key === promotionSort.key);
  if (!column) return promotionDimensionRows.value;
  const direction = promotionSort.order === 'asc' ? 1 : -1;
  const valueOf = (row) => {
    const value = row[column.key];
    if (column.key === 'imageUrl') return '';
    if (column.key === 'createdAt') return String(value || '');
    if (column.tone === 'number' || column.tone === 'rate') {
      const number = Number(value);
      return Number.isFinite(number) ? number : null;
    }
    return String(value ?? '').toLocaleLowerCase('zh-CN');
  };
  return [...promotionDimensionRows.value].sort((left, right) => {
    const a = valueOf(left);
    const b = valueOf(right);
    if (a === b) return String(left.linkId || '').localeCompare(String(right.linkId || ''));
    if (a === null || a === '') return 1;
    if (b === null || b === '') return -1;
    return (a < b ? -1 : 1) * direction;
  });
});
const promotionRangeHint = computed(() => `${promotionFilters.start || '—'} 至 ${promotionFilters.end || '—'}`);
const promotionDataCutoff = computed(() => promotionFilters.end && promotionFilters.end === availableDates.value.at(-1) ? '当前数据日' : '已结算数据');
const promotionSummary = computed(() => {
  const rows = promotionRows.value;
  const fallback = (key) => rows.reduce((sum, row) => sum + Number(row[key] || 0), 0);
  const summary = promotionApiSummary.value || {};
  const fromApi = (key, fallbackValue) => Object.prototype.hasOwnProperty.call(summary, key)
    ? Number(summary[key] || 0)
    : fallbackValue;
  const spend = fromApi('spend', fallback('promotionSpend'));
  const revenue = fromApi('revenue', fallback('promotionRevenue'));
  const orders = fromApi('promotionNetOrders', fallback('promotionNetOrders'));
  return { spend, revenue, orders, orderedProducts: rows.filter((row) => Number(row.promotionNetOrders || 0) > 0).length, roi: spend ? revenue / spend : 0 };
});
const promotionKpiCards = computed(() => {
  const rows = promotionRows.value;
  const apiSummary = promotionApiSummary.value || {};
  const total = (key) => rows.reduce((sum, row) => sum + Number(row[key] || 0), 0);
  const summaryTotal = (summaryKey, rowKey) => Object.prototype.hasOwnProperty.call(apiSummary, summaryKey)
    ? Number(apiSummary[summaryKey] || 0)
    : total(rowKey);
  const spend = summaryTotal('spend', 'promotionSpend');
  const revenue = summaryTotal('revenue', 'promotionRevenue');
  // 推广交易额来自推广事实表；订单收入单独绑定利润率表 orderAmount。
  const orderAmount = summaryTotal('orderAmount', 'orderAmount');
  const clicks = summaryTotal('clicks', 'clicks');
  const impressions = summaryTotal('impressions', 'impressions');
  const orders = promotionSummary.value.orders;
  const avgClickCost = clicks ? spend / clicks : 0;
  const avgOrderCost = orders ? spend / orders : 0;
  const conversionRate = clicks ? orders / clicks * 100 : 0;
  const clickRate = impressions ? clicks / impressions * 100 : 0;
  const netRevenue = summaryTotal('netRevenue', 'promotionNetRevenue');
  const directRevenue = total('directRevenue');
  const indirectRevenue = total('indirectRevenue');
  const favorites = total('favorites');
  const follows = total('follows');
  const inquiries = total('inquiries');
  const summary = linkSummaryTotals.value;
  return [
    { key: 'spend', label: '成交花费', value: formatPromotionMoney(spend), note: `推广商品 ${rows.length.toLocaleString()} 个` },
    { key: 'revenue', label: '推广交易额', value: formatPromotionMoney(revenue), note: `净成交笔数 ${orders.toLocaleString()}` },
    { key: 'orderAmount', label: '订单收入', value: formatPromotionMoney(orderAmount), note: '利润率表 orderAmount 合计' },
    { key: 'roi', label: '实际投产比', value: promotionSummary.value.roi.toFixed(2), note: '交易额 ÷ 成交花费' },
    { key: 'netRevenue', label: '净交易额', value: formatPromotionMoney(netRevenue), note: '剔除退款后的交易额' },
    { key: 'netRoi', label: '净实际投产比', value: spend ? (netRevenue / spend).toFixed(2) : '0.00', note: '净交易额 ÷ 成交花费' },
    { key: 'orders', label: '净成交笔数', value: orders.toLocaleString(), note: '当前数据范围' },
    { key: 'avgOrderCost', label: '每笔成交花费', value: formatPromotionMoney(avgOrderCost), note: '成交花费 ÷ 净成交笔数' },
    { key: 'avgClickCost', label: '平均点击成本', value: formatPromotionMoney(avgClickCost), note: '成交花费 ÷ 点击量' },
    { key: 'impressions', label: '曝光量', value: impressions.toLocaleString(), note: '当前数据范围' },
    { key: 'clicks', label: '点击量', value: clicks.toLocaleString(), note: '当前数据范围' },
    { key: 'clickRate', label: '点击率', value: `${clickRate.toFixed(2)}%`, note: '点击量 ÷ 曝光量' },
    { key: 'conversionRate', label: '点击转化率', value: `${conversionRate.toFixed(2)}%`, note: '净成交笔数 ÷ 点击量' },
    { key: 'directRevenue', label: '直接交易额', value: formatPromotionMoney(directRevenue), note: '直接成交归因' },
    { key: 'indirectRevenue', label: '间接交易额', value: formatPromotionMoney(indirectRevenue), note: '间接成交归因' },
    { key: 'favorites', label: '收藏量', value: favorites.toLocaleString(), note: '推广收藏行为' },
    { key: 'follows', label: '关注量', value: follows.toLocaleString(), note: '推广关注行为' },
    { key: 'inquiries', label: '询单量', value: inquiries.toLocaleString(), note: '推广询单行为' },
    { key: 'summaryLinks', label: '汇总链接数', value: summary.links.toLocaleString(), note: `${summary.rows.toLocaleString()} 行明细` },
    { key: 'summaryRevenue', label: '周期收入', value: `${formatSummaryWan(summary.revenue)}万`, note: `${summary.dataDays} 天` },
    { key: 'summaryCost', label: '货品成本', value: `${formatSummaryWan(summary.cost)}万`, note: `成本占比 ${formatSummaryPercent(summary.costPct)}` },
    { key: 'summaryGrossProfit', label: '毛利', value: `${formatSummaryWan(summary.grossProfit)}万`, note: `毛利率 ${formatSummaryPercent(summary.grossMargin)}` },
    { key: 'summaryPromotion', label: '推广费', value: `${formatSummaryWan(summary.promotion)}万`, note: `推广占比 ${formatSummaryPercent(summary.promotionPct)}` },
    { key: 'summaryPlatformProfit', label: '平台利润', value: `${formatSummaryWan(summary.platformProfit)}万`, note: `利润率 ${formatSummaryPercent(summary.profitRate)}` },
  ];
});
const promotionRowDrawerFields = Object.freeze([
  { key: 'storeName', label: '店铺名称', tone: 'text' },
  { key: 'linkId', label: '链接 ID', tone: 'text' },
  { key: 'productCode', label: '商品编码', tone: 'text' },
  { key: 'createdAt', label: '链接创建时间', tone: 'text' },
  { key: 'person', label: '负责人', tone: 'text' },
  { key: 'profitOrders', label: '利润单量', tone: 'count' },
  { key: 'orderAmount', label: '订单金额', tone: 'money' },
  { key: 'refundAmount', label: '退款金额', tone: 'money' },
  { key: 'goodsCost', label: '货品成本', tone: 'money' },
  { key: 'shippingCost', label: '快递成本', tone: 'money' },
  { key: 'afterRefundOrderAmount', label: '扣除退款订单金额', tone: 'money' },
  { key: 'afterReturnOrderAmount', label: '扣除退货率后订单金额', tone: 'money' },
  { key: 'afterReturnGoodsCost', label: '扣除退货率后货品成本', tone: 'money' },
  { key: 'costPct', label: '成本占比', tone: 'rate' },
  { key: 'afterReturnShippingCost', label: '扣除退货率后快递成本', tone: 'money' },
  { key: 'goodsShippingTotal', label: '货品快递总和', tone: 'money' },
  { key: 'goodsShippingPct', label: '货品快递总和占比', tone: 'rate' },
  { key: 'remoteSurcharge', label: '偏远加收', tone: 'money' },
  { key: 'grossProfit', label: '毛利', tone: 'money' },
  { key: 'grossMargin', label: '毛利率', tone: 'rate' },
  { key: 'techServiceFee', label: '技术服务费', tone: 'money' },
  { key: 'estimatedAfterSale', label: '预估售后', tone: 'money' },
  { key: 'profitPromotionFee', label: '推广费', tone: 'money' },
  { key: 'profitPromotionPct', label: '推广费占比', tone: 'rate' },
  { key: 'freightInsurance', label: '运费险', tone: 'money' },
  { key: 'tax', label: '税费', tone: 'money' },
  { key: 'platformProfit', label: '平台利润', tone: 'money' },
  { key: 'profitRate', label: '利润率', tone: 'rate' },
  { key: 'promotionSpend', label: '成交花费', tone: 'money' },
  { key: 'promotionTotalSpend', label: '总花费', tone: 'money' },
  { key: 'promotionRevenue', label: '推广交易额', tone: 'money' },
  { key: 'promotionRoi', label: '实际投产比', tone: 'ratio' },
  { key: 'promotionNetRoi', label: '净实际投产比', tone: 'ratio' },
  { key: 'promotionNetRevenue', label: '净交易额', tone: 'money' },
  { key: 'promotionNetOrders', label: '净成交笔数', tone: 'count' },
  { key: 'promotionAvgNetOrderSpend', label: '每笔净成交花费', tone: 'money' },
  { key: 'promotionNetRevenueRatio', label: '净交易额占比', tone: 'rate' },
  { key: 'promotionNetOrdersRatio', label: '净成交笔数占比', tone: 'rate' },
  { key: 'promotionAvgNetOrderRevenue', label: '每笔净成交金额', tone: 'money' },
  { key: 'settledRevenue', label: '结算交易额', tone: 'money' },
  { key: 'settledRoi', label: '结算投产比', tone: 'ratio' },
  { key: 'settledOrders', label: '结算成交笔数', tone: 'count' },
  { key: 'refundExemptionRate', label: '退款豁免率', tone: 'rate' },
  { key: 'cancelExemptionRate', label: '退单豁免率', tone: 'rate' },
  { key: 'settledAvgOrderSpend', label: '每笔结算成交花费', tone: 'money' },
  { key: 'revenueSettlementRate', label: '交易额结算率', tone: 'rate' },
  { key: 'orderSettlementRate', label: '订单结算率', tone: 'rate' },
  { key: 'settledAvgOrderRevenue', label: '每笔结算成交金额', tone: 'money' },
  { key: 'promotionOrders', label: '成交笔数', tone: 'count' },
  { key: 'promotionAvgOrderSpend', label: '每笔成交花费', tone: 'money' },
  { key: 'promotionAvgOrderRevenue', label: '每笔成交金额', tone: 'money' },
  { key: 'directRevenue', label: '直接交易额', tone: 'money' },
  { key: 'indirectRevenue', label: '间接交易额', tone: 'money' },
  { key: 'directOrders', label: '直接成交笔数', tone: 'count' },
  { key: 'indirectOrders', label: '间接成交笔数', tone: 'count' },
  { key: 'impressions', label: '曝光量', tone: 'count' },
  { key: 'clicks', label: '点击量', tone: 'count' },
  { key: 'sitePromotionRatio', label: '全站推广费比', tone: 'rate' },
  { key: 'dataDays', label: '数据天数', tone: 'count' },
]);
function promotionRowMetricDisplay(value, tone) {
  if (tone === 'count') return Math.round(Number(value || 0)).toLocaleString('zh-CN');
  if (tone === 'rate') return `${Number(value || 0).toFixed(2)}%`;
  if (tone === 'ratio') return Number(value || 0).toFixed(2);
  if (tone === 'money') return formatPromotionMoney(value);
  return String(value || '—');
}
function promotionRowMetricTone(metric) {
  const field = promotionRowDrawerFields.find((item) => item.key === metric);
  return field?.tone || 'money';
}
function promotionRowMetricValue(metric, item = {}) {
  const source = promotionMetricSource(item);
  return {
    storeName: item.storeName || '', linkId: item.linkId || '', productCode: item.productCode || '', createdAt: item.createdAt || '', person: item.person || '',
    profitOrders: item.profitOrders, orderAmount: item.orderAmount, refundAmount: item.refundAmount, goodsCost: item.goodsCost, shippingCost: item.shippingCost,
    grossProfit: item.grossProfit, grossMargin: item.grossMargin, platformProfit: item.platformProfit, profitRate: item.profitRate,
    promotionSpend: item.promotionSpend ?? source.spend, promotionTotalSpend: item.promotionTotalSpend, promotionRevenue: item.promotionRevenue ?? source.revenue,
    promotionRoi: item.promotionRoi ?? source.roi, promotionNetRevenue: item.promotionNetRevenue ?? source.netRevenue, promotionNetOrders: item.promotionNetOrders ?? source.orders,
    promotionOrders: item.promotionOrders, directRevenue: item.directRevenue ?? source.directRevenue, indirectRevenue: item.indirectRevenue ?? source.indirectRevenue,
    impressions: item.impressions ?? source.impressions, clicks: item.clicks ?? source.clicks, sitePromotionRatio: item.sitePromotionRatio,
    dataDays: item.dataDays ?? 1,
  }[metric] ?? item[metric] ?? 0;
}
const promotionRowDrawerCards = computed(() => {
  const row = promotionDrawerRow.value;
  if (!row) return [];
  const previous = promotionDrawerComparison.value.previousRow;
  return promotionRowDrawerFields.map((field) => {
    const currentValue = promotionRowMetricValue(field.key, row);
    const previousValue = previous ? promotionRowMetricValue(field.key, previous) : null;
    const isText = ['storeName', 'linkId', 'productCode', 'createdAt', 'person'].includes(field.key);
    return {
      key: field.key,
      label: field.label,
      value: promotionRowMetricDisplay(currentValue, field.tone),
      previousValue: promotionComparisonLoading.value ? '加载中…' : isText ? '—' : formatPeriodChange(currentValue, previousValue),
      previousTone: isText ? '' : periodChangeTone(currentValue, previousValue),
      note: field.key === 'linkId' ? '点击字段卡片查看每日变化' : '当前筛选周期',
    };
  });
});
const promotionSelectedKpiCard = computed(() => {
  const cards = promotionDrawerMode.value === 'row' ? promotionRowDrawerCards.value : promotionKpiCards.value;
  return cards.find((card) => card.key === promotionSelectedKpi.value) || cards[0] || { key: 'spend', label: '成交花费', value: '0.00', note: '' };
});
function promotionMetricSource(item = {}, fallback = {}) {
  const spend = Number(item.spend ?? item.promotionSpend ?? item.promotion ?? fallback.spend ?? 0);
  const revenue = Number(item.revenue ?? item.promotionRevenue ?? fallback.revenue ?? 0);
  const orders = Number(item.orders ?? item.promotionNetOrders ?? fallback.orders ?? 0);
  const clicks = Number(item.clicks ?? fallback.clicks ?? 0);
  const impressions = Number(item.impressions ?? fallback.impressions ?? 0);
  const netRevenue = Number(item.netRevenue ?? item.promotionNetRevenue ?? item.net_revenue ?? revenue);
  const directRevenue = Number(item.directRevenue ?? item.direct_revenue ?? 0);
  const indirectRevenue = Number(item.indirectRevenue ?? item.indirect_revenue ?? 0);
  const orderAmount = Number(item.orderAmount ?? item.summaryRevenue ?? fallback.orderAmount ?? 0);
  return {
    spend, revenue, orders, clicks, impressions, netRevenue, directRevenue, indirectRevenue, orderAmount,
    favorites: Number(item.favorites || 0), follows: Number(item.follows || 0), inquiries: Number(item.inquiries || 0),
    summaryLinks: Number(item.summaryLinks ?? 1),
    summaryRevenue: Number(item.summaryRevenue ?? orderAmount),
    summaryCost: Number(item.summaryCost ?? item.goodsCost ?? 0),
    summaryGrossProfit: Number(item.summaryGrossProfit ?? item.grossProfit ?? 0),
    summaryPromotion: Number(item.summaryPromotion ?? item.profitPromotionFee ?? 0),
    summaryPlatformProfit: Number(item.summaryPlatformProfit ?? item.platformProfit ?? 0),
  };
}
function promotionMetricValue(metric, source) {
  const clickRate = source.impressions ? source.clicks / source.impressions * 100 : 0;
  const conversionRate = source.clicks ? source.orders / source.clicks * 100 : 0;
  return { spend: source.spend, revenue: source.revenue, orderAmount: source.orderAmount, roi: source.spend ? source.revenue / source.spend : 0, netRevenue: source.netRevenue, netRoi: source.spend ? source.netRevenue / source.spend : 0, orders: source.orders, avgOrderCost: source.orders ? source.spend / source.orders : 0, avgClickCost: source.clicks ? source.spend / source.clicks : 0, impressions: source.impressions, clicks: source.clicks, clickRate, conversionRate, directRevenue: source.directRevenue, indirectRevenue: source.indirectRevenue, favorites: source.favorites, follows: source.follows, inquiries: source.inquiries, summaryLinks: source.summaryLinks, summaryRevenue: source.summaryRevenue, summaryCost: source.summaryCost, summaryGrossProfit: source.summaryGrossProfit, summaryPromotion: source.summaryPromotion, summaryPlatformProfit: source.summaryPlatformProfit }[metric] || 0;
}
function formatPromotionMetricDisplay(metric, value) {
  const amount = Number(value || 0);
  if (['clickRate', 'conversionRate'].includes(metric)) return `${amount.toFixed(2)}%`;
  if (['roi', 'netRoi'].includes(metric)) return amount.toFixed(2);
  if (['summaryRevenue', 'summaryCost', 'summaryGrossProfit', 'summaryPromotion', 'summaryPlatformProfit'].includes(metric)) return `${formatSummaryWan(amount)}万`;
  if (metric === 'summaryLinks') return Math.round(amount).toLocaleString();
  if (['orders', 'impressions', 'clicks', 'favorites', 'follows', 'inquiries'].includes(metric)) return Math.round(amount).toLocaleString();
  return formatPromotionMoney(amount);
}
function promotionMetricTotalsFromRows(rows, summaryOverride = null) {
  const linkIds = new Set(rows.map((row) => String(row.linkId || '')).filter((id) => id && !id.includes(':')));
  const total = (key) => rows.reduce((sum, row) => sum + Number(row[key] || 0), 0);
  return promotionMetricSource({
    spend: total('promotionSpend'), revenue: total('promotionRevenue'), orderAmount: total('orderAmount'), orders: total('promotionNetOrders'),
    clicks: total('clicks'), impressions: total('impressions'), netRevenue: total('promotionNetRevenue'),
    directRevenue: total('directRevenue'), indirectRevenue: total('indirectRevenue'), favorites: total('favorites'),
    follows: total('follows'), inquiries: total('inquiries'),
    summaryLinks: summaryOverride?.links ?? linkIds.size,
    summaryRevenue: summaryOverride?.revenue ?? total('orderAmount'),
    summaryCost: summaryOverride?.cost ?? total('goodsCost'),
    summaryGrossProfit: summaryOverride?.grossProfit ?? total('grossProfit'),
    summaryPromotion: summaryOverride?.promotion ?? total('profitPromotionFee'),
    summaryPlatformProfit: summaryOverride?.platformProfit ?? total('platformProfit'),
  });
}
const promotionMetricTotals = computed(() => promotionMetricTotalsFromRows(promotionRows.value, linkSummaryTotals.value));
const promotionComparisonMetricTotals = computed(() => promotionMetricTotalsFromRows(promotionComparisonRows.value));
function shiftPromotionDate(date, days) {
  if (!date) return '';
  const value = new Date(`${date}T00:00:00Z`);
  if (Number.isNaN(value.getTime())) return '';
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}
const promotionComparisonRange = computed(() => {
  const start = promotionFilters.start;
  const end = promotionFilters.end;
  if (!start || !end) return { start: '', end: '', days: 0, label: '' };
  const startMs = Date.parse(`${start}T00:00:00Z`);
  const endMs = Date.parse(`${end}T00:00:00Z`);
  const days = Number.isFinite(startMs) && Number.isFinite(endMs) ? Math.max(1, Math.round((endMs - startMs) / 86400000) + 1) : 0;
  const previousEnd = shiftPromotionDate(start, -1);
  const previousStart = shiftPromotionDate(start, -days);
  return { start: previousStart, end: previousEnd, days, label: previousStart && previousEnd ? `${previousStart} 至 ${previousEnd}` : '' };
});
const promotionComparisonDimensionRows = computed(() => {
  if (promotionDimension.value === 'link') return promotionComparisonRows.value;
  const groups = new Map();
  for (const row of promotionComparisonRows.value) {
    const value = promotionDimensionValue(row);
    const current = groups.get(value) || [];
    current.push(row);
    groups.set(value, current);
  }
  return [...groups.entries()].map(([value, rows]) => promotionAggregateRow(rows, value));
});
const promotionDrawerComparison = computed(() => {
  const currentRow = promotionDrawerRow.value;
  const previousRow = currentRow ? promotionComparisonDimensionRows.value.find((row) => String(row.linkId) === String(currentRow.linkId)) || null : null;
  const hasPreviousData = promotionComparisonRows.value.length > 0;
  return { previousDate: promotionComparisonRange.value.label, previous: hasPreviousData ? promotionComparisonMetricTotals.value : null, previousRow };
});
function formatPeriodChange(current, previous) {
  if (current === null || current === undefined || previous === null || previous === undefined || previous === '') return '—';
  const currentNumber = Number(current);
  const previousNumber = Number(previous);
  if (!Number.isFinite(currentNumber) || !Number.isFinite(previousNumber)) return '—';
  if (previousNumber === 0) return currentNumber === 0 ? '0.00%' : '新增';
  const change = (currentNumber - previousNumber) / Math.abs(previousNumber) * 100;
  return `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`;
}
function periodChangeTone(current, previous) {
  if (current === null || current === undefined || previous === null || previous === undefined || previous === '') return '';
  const currentNumber = Number(current);
  const previousNumber = Number(previous);
  if (!Number.isFinite(currentNumber) || !Number.isFinite(previousNumber) || previousNumber === 0) return '';
  return currentNumber >= previousNumber ? 'rate-positive' : 'rate-negative';
}
const promotionDrawerCards = computed(() => promotionKpiCards.value.map((card) => {
  const currentValue = promotionMetricValue(card.key, promotionMetricTotals.value);
  const previousValue = promotionDrawerComparison.value.previous ? promotionMetricValue(card.key, promotionDrawerComparison.value.previous) : null;
  return { ...card, previousValue: promotionComparisonLoading.value ? '加载中…' : formatPeriodChange(currentValue, previousValue), previousTone: periodChangeTone(currentValue, previousValue) };
}));
const activePromotionDrawerCards = computed(() => promotionDrawerMode.value === 'row' ? promotionRowDrawerCards.value : promotionDrawerCards.value);
function loadPromotionCardOrder() {
  if (typeof window === 'undefined') return [];
  try {
    const saved = JSON.parse(window.localStorage.getItem(promotionCardOrderStorageKey) || '[]');
    return Array.isArray(saved) ? saved.filter((key) => typeof key === 'string' && key) : [];
  } catch {
    return [];
  }
}
function persistPromotionCardOrder() {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(promotionCardOrderStorageKey, JSON.stringify(promotionCardOrder.value));
  } catch {
    // 本地存储不可用时仍保留当前会话内的拖动顺序。
  }
}
function ensurePromotionCardOrder(cards) {
  const incomingKeys = cards.map((card) => card?.key).filter(Boolean);
  const knownKeys = new Set(promotionCardOrder.value);
  const missingKeys = incomingKeys.filter((key) => !knownKeys.has(key));
  if (!missingKeys.length) return;
  promotionCardOrder.value = [...promotionCardOrder.value, ...missingKeys];
  persistPromotionCardOrder();
}
function orderedPromotionCards(cards) {
  const order = new Map(promotionCardOrder.value.map((key, index) => [key, index]));
  return [...cards].sort((left, right) => {
    const leftIndex = order.get(left.key) ?? Number.MAX_SAFE_INTEGER;
    const rightIndex = order.get(right.key) ?? Number.MAX_SAFE_INTEGER;
    return leftIndex - rightIndex;
  });
}
function movePromotionCardBefore(targetKey) {
  const sourceKey = promotionCardDragKey.value;
  if (!sourceKey || !targetKey || sourceKey === targetKey) return false;
  const nextOrder = [...promotionCardOrder.value];
  const sourceIndex = nextOrder.indexOf(sourceKey);
  const targetIndex = nextOrder.indexOf(targetKey);
  if (sourceIndex < 0 || targetIndex < 0) return false;
  nextOrder.splice(sourceIndex, 1);
  const nextTargetIndex = nextOrder.indexOf(targetKey);
  if (nextTargetIndex < 0) return false;
  nextOrder.splice(nextTargetIndex, 0, sourceKey);
  promotionCardOrder.value = nextOrder;
  persistPromotionCardOrder();
  return true;
}
function startPromotionCardPointerDrag(event, key) {
  if (event?.pointerType === 'mouse' && event.button !== 0) return;
  promotionCardDragKey.value = key;
  promotionCardPointerMoved.value = false;
}
function handlePromotionCardPointerEnter(targetKey) {
  if (!promotionCardDragKey.value || promotionCardDragKey.value === targetKey) return;
  if (movePromotionCardBefore(targetKey)) promotionCardPointerMoved.value = true;
}
function endPromotionCardPointerDrag() {
  if (promotionCardPointerMoved.value) {
    promotionCardSuppressClick.value = true;
    window.setTimeout(() => { promotionCardSuppressClick.value = false; }, 0);
  }
  endPromotionCardDrag();
}
function handlePromotionCardClick(event, key) {
  if (promotionCardSuppressClick.value) {
    event.preventDefault();
    promotionCardSuppressClick.value = false;
    return;
  }
  if (promotionDrawerMode.value === 'row') openPromotionTrend(key);
  else openPromotionKpiTrend(key);
}
function endPromotionCardDrag() {
  promotionCardDragKey.value = '';
}
watch([promotionKpiCards, promotionRowDrawerCards], ([mainCards, drawerCards]) => {
  ensurePromotionCardOrder([...mainCards, ...drawerCards]);
}, { immediate: true });
const promotionExpandedRow = computed(() => promotionDimensionRows.value.find((item) => item.linkId === promotionExpandedKey.value) || null);
// 这些字段来自推广日事实表；利润表字段仍然使用原来的日粒度数据。
const promotionHourlyMetricKeys = new Set([
  'promotionSpend', 'promotionTotalSpend', 'promotionRevenue', 'promotionRoi', 'promotionNetRoi', 'promotionNetRevenue',
  'promotionNetOrders', 'promotionAvgNetOrderSpend', 'promotionNetRevenueRatio', 'promotionNetOrdersRatio', 'promotionAvgNetOrderRevenue',
  'settledRevenue', 'settledRoi', 'settledOrders', 'refundExemptionRate', 'cancelExemptionRate', 'settledAvgOrderSpend',
  'revenueSettlementRate', 'orderSettlementRate', 'settledAvgOrderRevenue', 'promotionOrders', 'promotionAvgOrderSpend',
  'promotionAvgOrderRevenue', 'directRevenue', 'indirectRevenue', 'directOrders', 'indirectOrders', 'impressions', 'clicks',
  'sitePromotionRatio',
]);
const promotionHourlyNumericFields = Object.freeze([...promotionHourlyMetricKeys]);
function promotionHourlyNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}
function promotionHourlyMetricSource(item = {}) {
  return {
    promotionSpend: promotionHourlyNumber(item.spend),
    promotionTotalSpend: promotionHourlyNumber(item.totalSpend),
    promotionRevenue: promotionHourlyNumber(item.revenue),
    promotionRoi: promotionHourlyNumber(item.roi),
    promotionNetRoi: promotionHourlyNumber(item.netRoi),
    promotionNetRevenue: promotionHourlyNumber(item.netRevenue),
    promotionNetOrders: promotionHourlyNumber(item.netOrders),
    promotionAvgNetOrderSpend: promotionHourlyNumber(item.avgNetOrderSpend),
    promotionNetRevenueRatio: promotionHourlyNumber(item.netRevenueRatio),
    promotionNetOrdersRatio: promotionHourlyNumber(item.netOrdersRatio),
    promotionAvgNetOrderRevenue: promotionHourlyNumber(item.avgNetOrderRevenue),
    settledRevenue: promotionHourlyNumber(item.settledRevenue),
    settledRoi: promotionHourlyNumber(item.settledRoi),
    settledOrders: promotionHourlyNumber(item.settledOrders),
    refundExemptionRate: promotionHourlyNumber(item.refundExemptionRate),
    cancelExemptionRate: promotionHourlyNumber(item.cancelExemptionRate),
    settledAvgOrderSpend: promotionHourlyNumber(item.settledAvgOrderSpend),
    revenueSettlementRate: promotionHourlyNumber(item.revenueSettlementRate),
    orderSettlementRate: promotionHourlyNumber(item.orderSettlementRate),
    settledAvgOrderRevenue: promotionHourlyNumber(item.settledAvgOrderRevenue),
    promotionOrders: promotionHourlyNumber(item.orders),
    promotionAvgOrderSpend: promotionHourlyNumber(item.avgOrderSpend),
    promotionAvgOrderRevenue: promotionHourlyNumber(item.avgOrderRevenue),
    directRevenue: promotionHourlyNumber(item.directRevenue),
    indirectRevenue: promotionHourlyNumber(item.indirectRevenue),
    directOrders: promotionHourlyNumber(item.directOrders),
    indirectOrders: promotionHourlyNumber(item.indirectOrders),
    impressions: promotionHourlyNumber(item.impressions),
    clicks: promotionHourlyNumber(item.clicks),
    sitePromotionRatio: promotionHourlyNumber(item.sitePromotionRatio),
  };
}
function promotionHourlySlotList(range) {
  const start = String(range?.start || '').slice(0, 10);
  const end = String(range?.end || '').slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(start) || !/^\d{4}-\d{2}-\d{2}$/.test(end) || start > end) return [];
  const slots = [];
  const cursor = new Date(`${start}T00:00:00Z`);
  const last = new Date(`${end}T00:00:00Z`);
  while (cursor <= last) {
    const date = cursor.toISOString().slice(0, 10);
    for (let hour = 0; hour < 24; hour += 1) {
      const hourLabel = `${String(hour).padStart(2, '0')}:00`;
      slots.push({ date, hour: hourLabel, hourLabel: `${date} ${hourLabel}`, key: `${date}-${hourLabel}` });
    }
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return slots;
}
function buildPromotionHourlyDrawerRows(hourlyRows, range, fillMissing = false) {
  const grouped = new Map();
  for (const item of hourlyRows || []) {
    const date = String(item.date || '').slice(0, 10);
    const match = String(item.hour || '').match(/\d{1,2}/);
    const hour = match ? `${String(Number(match[0])).padStart(2, '0')}:00` : '';
    if (!date || !hour || (range.start && date < range.start) || (range.end && date > range.end)) continue;
    const key = `${date}-${hour}`;
    const current = grouped.get(key) || { date, hour, hourLabel: `${date} ${hour}`, key };
    const source = promotionHourlyMetricSource(item);
    for (const field of promotionHourlyNumericFields) current[field] = Number(current[field] || 0) + source[field];
    grouped.set(key, current);
  }
  if (!grouped.size && !fillMissing) return [];
  const slots = fillMissing ? promotionHourlySlotList(range) : [...grouped.values()].sort((a, b) => a.key.localeCompare(b.key));
  return slots.map((slot, index, all) => {
    const item = { ...slot, ...(grouped.get(slot.key) || {}) };
    // 聚合后重新计算比率和单笔指标，避免把每个小时的比例直接相加。
    const spend = Number(item.promotionSpend || 0);
    const revenue = Number(item.promotionRevenue || 0);
    const netRevenue = Number(item.promotionNetRevenue || 0);
    const orders = Number(item.promotionOrders || 0);
    const netOrders = Number(item.promotionNetOrders || 0);
    item.promotionRoi = spend ? revenue / spend : 0;
    item.promotionNetRoi = spend ? netRevenue / spend : 0;
    item.promotionAvgNetOrderSpend = netOrders ? spend / netOrders : 0;
    item.promotionNetRevenueRatio = revenue ? netRevenue / revenue * 100 : 0;
    item.promotionNetOrdersRatio = orders ? netOrders / orders * 100 : 0;
    item.promotionAvgNetOrderRevenue = netOrders ? netRevenue / netOrders : 0;
    item.promotionAvgOrderSpend = orders ? spend / orders : 0;
    item.promotionAvgOrderRevenue = orders ? revenue / orders : 0;
    const value = promotionRowMetricValue(promotionSelectedKpi.value, item);
    const previous = index ? promotionRowMetricValue(promotionSelectedKpi.value, all[index - 1]) : null;
    const change = previous == null ? '—' : `${value - previous >= 0 ? '+' : ''}${promotionRowMetricDisplay(value - previous, promotionRowMetricTone(promotionSelectedKpi.value))}`;
    return { ...item, value, display: promotionRowMetricDisplay(value, promotionRowMetricTone(promotionSelectedKpi.value)), change, changeTone: previous == null ? '' : value >= previous ? 'rate-positive' : 'rate-negative' };
  });
}
function buildPromotionDrawerRows(dailyRows, range) {
  const grouped = new Map();
  for (const item of dailyRows) {
    const date = String(item.dataDate || '').slice(0, 10);
    if (!date || (range.start && date < range.start) || (range.end && date > range.end)) continue;
    const source = promotionMetricSource(item);
    source.summaryLinks = item.orderAmount == null ? 0 : 1;
    const current = grouped.get(date) || {
      ...source,
      ...(promotionDrawerMode.value === 'row'
        ? Object.fromEntries(promotionRowDrawerFields.filter((field) => field.tone !== 'text').map((field) => [field.key, 0]))
        : {}),
      date,
      hour: date,
      hourLabel: date,
    };
    for (const key of ['spend', 'revenue', 'orders', 'clicks', 'impressions', 'netRevenue', 'directRevenue', 'indirectRevenue', 'favorites', 'follows', 'inquiries']) current[key] += source[key];
    if (promotionDrawerMode.value === 'row') {
      // 行级抽屉按日期汇总时，同时累计利润表字段，确保切换任意字段后趋势都有对应值。
      for (const field of promotionRowDrawerFields) {
        if (field.tone !== 'text') current[field.key] += Number(item[field.key] || 0);
      }
      const orderAmount = Number(current.orderAmount || 0);
      const goodsCost = Number(current.goodsCost || 0);
      const shippingCost = Number(current.shippingCost || 0);
      const promotionSpend = Number(current.promotionSpend || 0);
      const promotionRevenue = Number(current.promotionRevenue || 0);
      current.afterRefundOrderAmount = orderAmount - Number(current.refundAmount || 0);
      current.goodsShippingTotal = goodsCost + shippingCost;
      current.costPct = ratio(goodsCost, orderAmount);
      current.goodsShippingPct = ratio(current.goodsShippingTotal, orderAmount);
      current.grossMargin = ratio(current.grossProfit, orderAmount);
      current.profitPromotionPct = ratio(promotionSpend, orderAmount);
      current.profitRate = ratio(current.platformProfit, orderAmount);
      current.promotionRoi = promotionSpend ? promotionRevenue / promotionSpend : 0;
      current.promotionNetRoi = promotionSpend ? Number(current.promotionNetRevenue || 0) / promotionSpend : 0;
      current.settledRoi = Number(current.settledAvgOrderSpend || 0) ? Number(current.settledRevenue || 0) / Number(current.settledAvgOrderSpend || 0) : 0;
    }
    grouped.set(date, current);
  }
  return [...grouped.values()].sort((a, b) => a.date.localeCompare(b.date)).map((item, index, all) => {
    const value = promotionDrawerMode.value === 'row' ? promotionRowMetricValue(promotionSelectedKpi.value, item) : promotionMetricValue(promotionSelectedKpi.value, item);
    const previous = index ? (promotionDrawerMode.value === 'row' ? promotionRowMetricValue(promotionSelectedKpi.value, all[index - 1]) : promotionMetricValue(promotionSelectedKpi.value, all[index - 1])) : null;
    const change = previous == null ? '—' : `${value - previous >= 0 ? '+' : ''}${promotionDrawerMode.value === 'row' ? promotionRowMetricDisplay(value - previous, promotionRowMetricTone(promotionSelectedKpi.value)) : formatPromotionMetricDisplay(promotionSelectedKpi.value, value - previous)}`;
    return { ...item, key: item.date, value, display: promotionDrawerMode.value === 'row' ? promotionRowMetricDisplay(value, promotionRowMetricTone(promotionSelectedKpi.value)) : formatPromotionMetricDisplay(promotionSelectedKpi.value, value), change, changeTone: previous == null ? '' : value >= previous ? 'rate-positive' : 'rate-negative' };
  });
}
const promotionDrawerHasHourlySource = computed(() => Boolean(promotionDrawerMode.value === 'row'
  && promotionDrawerHourlyLoaded.value
  && (promotionDrawerHourlySourceRows.value.length || promotionDrawerPreviousHourlySourceRows.value.length)));
const promotionDrawerUsesHourlyMetric = computed(() => promotionDrawerHasHourlySource.value && promotionHourlyMetricKeys.has(promotionSelectedKpi.value));
const promotionDrawerGranularityHint = computed(() => promotionDrawerUsesHourlyMetric.value ? '推广日数据（数据日期）' : '利润日数据（数据日期）');
const promotionDrawerTimeColumnLabel = computed(() => promotionDrawerUsesHourlyMetric.value ? '数据日期 + 小时' : '数据日期');
const promotionDrawerComparisonColumnLabel = computed(() => promotionDrawerUsesHourlyMetric.value ? '对比日期 + 小时' : '对比日期');
const promotionDrawerHourlyRows = computed(() => {
  if (promotionDrawerUsesHourlyMetric.value) {
    return buildPromotionHourlyDrawerRows(
      promotionDrawerHourlySourceRows.value,
      { start: promotionFilters.start, end: promotionFilters.end },
      Boolean(promotionDrawerHourlySourceRows.value.length || promotionDrawerPreviousHourlySourceRows.value.length),
    );
  }
  const dailyRows = promotionDrawerMode.value === 'row' ? (promotionDrawerRow.value?.dailyRows || []) : promotionRows.value.flatMap((row) => row.dailyRows || []);
  return buildPromotionDrawerRows(dailyRows, { start: promotionFilters.start, end: promotionFilters.end });
});
const promotionDrawerPreviousHourlyRows = computed(() => {
  if (promotionDrawerUsesHourlyMetric.value) {
    return buildPromotionHourlyDrawerRows(
      promotionDrawerPreviousHourlySourceRows.value,
      promotionComparisonRange.value,
      Boolean(promotionDrawerHourlySourceRows.value.length || promotionDrawerPreviousHourlySourceRows.value.length),
    );
  }
  const previous = promotionDrawerMode.value === 'row' ? promotionDrawerComparison.value.previousRow : null;
  const dailyRows = promotionDrawerMode.value === 'row' ? (previous?.dailyRows || []) : promotionComparisonRows.value.flatMap((row) => row.dailyRows || []);
  return buildPromotionDrawerRows(dailyRows, promotionComparisonRange.value);
});
function buildPromotionTrendPoints(currentRows, comparisonRows) {
  const slotCount = Math.max(currentRows.length, comparisonRows.length);
  if (!slotCount) return { current: [], comparison: [] };
  const values = [...currentRows, ...comparisonRows].map((row) => Number(row.value || 0));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const width = 920;
  const height = 190;
  const pointY = (value) => 40 + (1 - (Number(value || 0) - min) / span) * height;
  const pointX = (index) => slotCount === 1 ? width / 2 : index / (slotCount - 1) * width;
  const current = currentRows.map((row, index) => {
    const compare = comparisonRows[index];
    return { ...row, x: pointX(index), y: pointY(row.value), tooltip: `当前周期 ${row.date}：${row.display}\\n对比周期 ${compare?.date || '—'}：${compare?.display || '—'}` };
  });
  const comparison = comparisonRows.map((row, index) => {
    const current = currentRows[index];
    return { ...row, x: pointX(index), y: pointY(row.value), key: `comparison-${row.key}`, tooltip: `对比周期 ${row.date}：${row.display}\\n当前周期 ${current?.date || '—'}：${current?.display || '—'}` };
  });
  return { current, comparison };
}
const promotionDrawerTrendPoints = computed(() => buildPromotionTrendPoints(promotionDrawerHourlyRows.value, promotionDrawerPreviousHourlyRows.value));
const promotionHoveredTrendPoint = ref(null);
const promotionTrendTooltipStyle = computed(() => {
  const point = promotionHoveredTrendPoint.value;
  if (!point) return {};
  const left = Math.min(86, Math.max(14, point.x / 920 * 100));
  const top = point.y / 270 * 100;
  return { left: `${left}%`, top: `${Math.max(4, top - 2)}%` };
});
function showPromotionTrendTooltip(point, series, index) {
  const comparePoint = series === 'current' ? promotionDrawerPreviousHourlyPointsList.value[index] : promotionDrawerHourlyPointsList.value[index];
  promotionHoveredTrendPoint.value = {
    ...point,
    seriesLabel: series === 'current' ? '当前周期' : '对比周期',
    compareSeriesLabel: series === 'current' ? '对比周期' : '当前周期',
    compareDate: comparePoint?.date || '',
    compareDisplay: comparePoint?.display || '—',
  };
}
function handlePromotionTrendPointerMove(event) {
  const points = promotionDrawerHourlyPointsList.value;
  if (!points.length) return;
  const rect = event.currentTarget?.getBoundingClientRect?.();
  if (!rect?.width) return;
  const chartX = Math.min(920, Math.max(0, (event.clientX - rect.left) / rect.width * 920));
  let nearestIndex = 0;
  let nearestDistance = Number.POSITIVE_INFINITY;
  points.forEach((point, index) => {
    const distance = Math.abs(point.x - chartX);
    if (distance < nearestDistance) {
      nearestDistance = distance;
      nearestIndex = index;
    }
  });
  showPromotionTrendTooltip(points[nearestIndex], 'current', nearestIndex);
}
function hidePromotionTrendTooltip() {
  promotionHoveredTrendPoint.value = null;
}
const promotionDrawerHourlyPointsList = computed(() => {
  return promotionDrawerTrendPoints.value.current;
});
const promotionDrawerHourlyPoints = computed(() => promotionDrawerHourlyPointsList.value.map((point) => `${point.x},${point.y}`).join(' '));
const promotionDrawerPreviousHourlyPointsList = computed(() => promotionDrawerTrendPoints.value.comparison);
const promotionDrawerPreviousHourlyPoints = computed(() => promotionDrawerPreviousHourlyPointsList.value.map((point) => `${point.x},${point.y}`).join(' '));
function promotionDrawerComparisonDate(item, index) {
  const previousDate = promotionDrawerPreviousHourlyRows.value[index]?.hourLabel;
  if (previousDate) return previousDate;
  const days = promotionComparisonRange.value.days;
  return days ? shiftPromotionDate(item?.hourLabel || item?.date, -days) || '—' : '—';
}
const promotionTrendRows = computed(() => promotionDrawerHourlyRows.value);
const promotionTrendPointsList = computed(() => {
  const rows = promotionTrendRows.value;
  if (!rows.length) return [];
  const values = rows.map((row) => row.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const width = 900;
  const height = 190;
  return rows.map((row, index) => ({ ...row, x: rows.length === 1 ? width / 2 : index / (rows.length - 1) * width, y: 12 + (1 - (row.value - min) / span) * height }));
});
const promotionTrendPoints = computed(() => promotionTrendPointsList.value.map((point) => `${point.x},${point.y}`).join(' '));
const promotionTrendGridLines = Object.freeze([{ y: 12 }, { y: 59.5 }, { y: 107 }, { y: 154.5 }, { y: 202 }]);
function openPromotionKpiTrend(key) {
  promotionDrawerMode.value = 'kpi';
  promotionDrawerRow.value = null;
  openPromotionTrend(key);
}
function openPromotionRowDrawer(row) {
  promotionDrawerMode.value = 'row';
  promotionDrawerRow.value = row;
  promotionSelectedKpi.value = 'orderAmount';
  promotionDrawerTab.value = 'trend';
  promotionTrendOpen.value = true;
  loadPromotionDrawerHourlyData(row);
}
function openPromotionTrend(key) {
  promotionSelectedKpi.value = key;
  promotionDrawerTab.value = 'trend';
  promotionTrendOpen.value = true;
}
function closePromotionDrawer() {
  promotionTrendOpen.value = false;
  promotionDrawerMode.value = 'kpi';
  promotionDrawerRow.value = null;
  promotionDrawerHourlyRequestKey.value = '';
  promotionDrawerHourlyLoading.value = false;
  promotionDrawerHourlyLoaded.value = false;
  promotionDrawerHourlySourceRows.value = [];
  promotionDrawerPreviousHourlySourceRows.value = [];
  promotionDrawerHourlyError.value = '';
}
const promotionPages = computed(() => Math.ceil(promotionDimensionRows.value.length / Math.max(1, promotionPageSize.value)));
const pagedPromotionRows = computed(() => {
  const pages = promotionPages.value;
  if (pages && promotionPage.value > pages) promotionPage.value = pages;
  const start = (Math.max(1, promotionPage.value) - 1) * promotionPageSize.value;
  return sortedPromotionRows.value.slice(start, start + promotionPageSize.value);
});
// 表头“全选”针对当前筛选结果集，而不是当前分页。由于 promotionRows 已经按筛选条件完整加载，
// 这里用全部排序后的结果判断状态，切换分页时勾选状态就能继续保持。
const allPromotionSelected = computed(() => sortedPromotionRows.value.length > 0 && sortedPromotionRows.value.every((row) => selectedPromotionIds.value.includes(row.linkId)));
const promotionExpandedModeLabel = computed(() => ({ detail: '推广详情', data: '数据明细', more: '更多操作' }[promotionExpandedMode.value] || '推广详情'));
const promotionHourOptions = Object.freeze(Array.from({ length: 24 }, (_, index) => String(index).padStart(2, '0')));
const promotionHourlyDates = computed(() => [...new Set(promotionHourlySourceRows.value.map((item) => String(item.date || '').slice(0, 10)).filter(Boolean))].sort());
const promotionHourlyRows = computed(() => {
  return promotionHourlySourceRows.value.filter((item) => {
    const dateMatch = promotionHourDate.value === 'all' || String(item.date || '').slice(0, 10) === promotionHourDate.value;
    const hourMatch = promotionHourPreset.value === 'all' || String(item.hour || '').startsWith(promotionHourPreset.value);
    return dateMatch && hourMatch;
  });
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
  if (key === 'promotion' && !promotionRows.value.length) {
    if (!promotionFilters.start && availableDates.value.length) {
      const [start, end] = promotionDateBounds(30);
      promotionFilters.start = start;
      promotionFilters.end = end;
    }
    rebuildPromotionRows();
  }
  if (key === 'promotion') {
    refreshPromotionLinkViews();
  }
}
function promotionDateBounds(days = 30) {
  const dates = availableDates.value;
  if (!dates.length) return ['', ''];
  const end = dates.at(-1);
  return [dates[Math.max(0, dates.length - Math.max(1, days))] || dates[0], end];
}
function standardFilterRowValue(row, field) {
  const aliases = {
    '链接id': 'linkId', '链接 ID': 'linkId', '商品编码': 'productCode', '商品名称': 'title', '商品标题': 'title',
    '店铺名称': 'storeName', '品牌': 'brand', '负责人': 'person', '链接创建时间': 'createdAt', '在售状态': 'saleStatus', '是否在售': 'saleStatus', '数据日期': 'lastDate',
    '单量': 'profitOrders', '利润单量': 'profitOrders', '收入': 'orderAmount', '订单金额': 'orderAmount', '订单金额(元)': 'orderAmount',
    '毛利': 'grossProfit', '毛利率': 'grossMargin', '平台利润': 'platformProfit', '利润率': 'profitRate',
    '推广费': 'profitPromotionFee', '推广费占比': 'profitPromotionPct', '成交花费': 'promotionSpend', '实际投产比': 'promotionRoi',
    '总花费(元)': 'promotionTotalSpend', '交易额(元)': 'promotionRevenue', '净交易额(元)': 'promotionNetRevenue', '净成交笔数': 'promotionNetOrders',
    '曝光量': 'impressions', '点击量': 'clicks', '全站推广费比': 'sitePromotionRatio',
  };
  return row[aliases[field] || field];
}
function normalizeFilterDate(value) {
  const text = String(value || '').slice(0, 10);
  return /^\d{8}$/.test(text) ? `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}` : text;
}
function matchesStandardFilter(row, filter) {
  const rawValue = standardFilterRowValue(row, filter.field);
  const type = linkColumnOptions.value.find((column) => column.key === filter.field)?.type || 'text';
  const value = rawValue == null ? '' : String(rawValue);
  const v1 = String(filter.v1 || '').trim();
  const v2 = String(filter.v2 || '').trim();
  if (!v1 && !v2) return true;
  if (filter.field === '链接id' || filter.field === '链接 ID') {
    const ids = v1.split(/[,，]/).map((item) => item.trim()).filter(Boolean);
    return ids.includes(String(row.linkId || '').trim());
  }
  if (type === 'number') {
    const number = Number(rawValue);
    if (!Number.isFinite(number)) return false;
    const min = v1 ? Number(v1) : null;
    const max = v2 ? Number(v2) : null;
    if (filter.op === 'eq' || filter.op === 'equals') return min == null || number === min;
    if (filter.op === 'gte') return min == null || number >= min;
    if (filter.op === 'lte') return min == null || number <= min;
    return (min == null || number >= min) && (max == null || number <= max);
  }
  if (type === 'date') {
    const actual = normalizeFilterDate(value);
    if (filter.op === 'gte') return !v1 || actual >= v1;
    if (filter.op === 'lte') return !v1 || actual <= v1;
    if (filter.op === 'between') return (!v1 || actual >= v1) && (!v2 || actual <= v2);
    return actual === v1;
  }
  return filter.op === 'equals' || filter.op === 'eq' ? value === v1 : value.toLocaleLowerCase('zh-CN').includes(v1.toLocaleLowerCase('zh-CN'));
}
function filterPromotionRowsByPreset(rows) {
  const filters = activeLinkPresetFilters.value;
  return filters.length ? rows.filter((row) => filters.every((filter) => matchesStandardFilter(row, filter))) : rows;
}
async function applyLinkPreset() {
  const preset = linkFilterPresets.value.find((item) => item.id === String(activeLinkPresetId.value));
  activeLinkPresetFilters.value = preset?.filters ? preset.filters.map((filter) => ({ ...filter })) : [];
  linkFilters.splice(0, linkFilters.length, ...activeLinkPresetFilters.value.map((filter, index) => ({ ...filter, id: `preset-${index}` })));
  promotionPage.value = 1;
  promotionExpandedKey.value = '';
  await applyRange();
}
function setPromotionDatePreset(key) {
  promotionDatePreset.value = key;
  const days = key === 'today' ? 1 : key === 'yesterday' ? 2 : key === '7d' ? 7 : key === '90d' ? 90 : 30;
  const [start, end] = promotionDateBounds(days);
  promotionFilters.start = key === 'yesterday' && availableDates.value.length > 1 ? availableDates.value.at(-2) : start;
  promotionFilters.end = key === 'yesterday' && availableDates.value.length > 1 ? availableDates.value.at(-2) : end;
  applyPromotionFilters();
}
async function rebuildPromotionRows() {
  promotionLoading.value = true;
  try {
    const response = await loadLinkOperatingSummary({
      page: 1,
      size: 20000,
      start: promotionFilters.start,
      end: promotionFilters.end,
      search: promotionFilters.search,
      link_ids: globalFilters.link_ids,
      product_code: globalFilters.product_code,
      product_name: globalFilters.product_name,
      brand: promotionFilters.brand || globalFilters.brand,
      store_name: globalFilters.store_name,
      store_person: globalFilters.store_person,
      sale_status: globalFilters.sale_status,
      ...creationParams(),
      ...ordersFilterParams(),
      filter_json: globalCustomFilterJson(),
    });
    if (!response?.success) throw new Error(response?.error || '链接经营数据加载失败');
    promotionApiSummary.value = response.summary || {};
    const rows = filterPromotionRowsByPreset((response.data || []).filter((row) => {
      if (promotionFilters.status && row.status !== promotionFilters.status) return false;
      if (promotionFilters.stage && row.stage !== promotionFilters.stage) return false;
      return true;
    }));
    promotionRows.value = rows;
    promotionPage.value = Math.min(promotionPage.value, Math.max(1, Math.ceil(rows.length / promotionPageSize.value)));
    selectedPromotionIds.value = selectedPromotionIds.value.filter((id) => rows.some((row) => row.linkId === id));
    await rebuildPromotionComparison();
  } catch (err) {
    promotionRows.value = [];
    promotionApiSummary.value = {};
    promotionComparisonRows.value = [];
    promotionNotice(err.message || '推广数据加载失败');
  } finally {
    promotionLoading.value = false;
  }
}
async function rebuildPromotionComparison() {
  const range = promotionComparisonRange.value;
  if (!range.start || !range.end) {
    promotionComparisonRows.value = [];
    promotionComparisonRequestKey.value = '';
    return;
  }
  const requestKey = JSON.stringify({
    start: range.start,
    end: range.end,
    search: promotionFilters.search,
    link_ids: globalFilters.link_ids,
    product_code: globalFilters.product_code,
    product_name: globalFilters.product_name,
    brand: promotionFilters.brand || globalFilters.brand,
    store_name: globalFilters.store_name,
    store_person: globalFilters.store_person,
    sale_status: globalFilters.sale_status,
    orders: globalFilters.orders,
    creation: creationParams(),
    customFilters: activeLinkPresetFilters.value,
  });
  if (requestKey === promotionComparisonRequestKey.value) return;
  promotionComparisonRequestKey.value = requestKey;
  promotionComparisonLoading.value = true;
  promotionComparisonError.value = '';
  try {
    const response = await loadLinkOperatingSummary({
      page: 1,
      size: 20000,
      start: range.start,
      end: range.end,
      search: promotionFilters.search,
      link_ids: globalFilters.link_ids,
      product_code: globalFilters.product_code,
      product_name: globalFilters.product_name,
      brand: promotionFilters.brand || globalFilters.brand,
      store_name: globalFilters.store_name,
      store_person: globalFilters.store_person,
      sale_status: globalFilters.sale_status,
      ...creationParams(),
      ...ordersFilterParams(),
      filter_json: globalCustomFilterJson(),
    });
    if (!response?.success) throw new Error(response?.error || '对比周期数据加载失败');
    promotionComparisonRows.value = filterPromotionRowsByPreset(response.data || []);
  } catch (err) {
    promotionComparisonRows.value = [];
    promotionComparisonError.value = err.message || '对比周期数据加载失败';
  } finally {
    promotionComparisonLoading.value = false;
  }
}
function applyPromotionFilters() {
  if (promotionFilters.start && promotionFilters.end && promotionFilters.start > promotionFilters.end) [promotionFilters.start, promotionFilters.end] = [promotionFilters.end, promotionFilters.start];
  promotionPage.value = 1;
  promotionExpandedKey.value = '';
  rebuildPromotionRows();
}
function setPromotionDimension(key) {
  if (!promotionDimensions.some((item) => item.key === key) || promotionDimension.value === key) return;
  promotionDimension.value = key;
  promotionPage.value = 1;
  promotionExpandedKey.value = '';
  selectedPromotionIds.value = [];
}
function clearPromotionFilters() {
  Object.assign(promotionFilters, { search: '', status: '', bidType: '', stage: '', brand: '' });
  setPromotionDatePreset('30d');
}
function toggleAllPromotion(event) {
  const resultIds = sortedPromotionRows.value.map((row) => row.linkId);
  selectedPromotionIds.value = event.target.checked
    ? [...new Set([...selectedPromotionIds.value, ...resultIds])]
    : selectedPromotionIds.value.filter((id) => !resultIds.includes(id));
}
async function togglePromotionDetails(row, mode) {
  if (promotionExpandedKey.value === row.linkId && promotionExpandedMode.value === mode) return closePromotionDetails();
  promotionExpandedKey.value = row.linkId;
  promotionExpandedMode.value = mode;
  promotionHourPreset.value = 'all';
  promotionHourDate.value = 'all';
  promotionHourlySourceRows.value = [];
  promotionHourlyError.value = '';
  if (mode !== 'data' || promotionDimension.value !== 'link') return;
  promotionHourlyLoading.value = true;
  try {
    const response = await loadPromotionHourly({
      link_id: row.linkId,
      product_id: row.linkId,
      product_name: row.title,
      store_name: row.storeName || '',
      start: promotionFilters.start,
      end: promotionFilters.end,
    });
    promotionHourlySourceRows.value = response?.data || [];
    promotionHourDate.value = promotionHourlyDates.value[0] || 'all';
  } catch (err) {
    promotionHourlyError.value = err.message || '推广日数据加载失败';
  } finally {
    promotionHourlyLoading.value = false;
  }
}
async function loadPromotionDrawerHourlyData(row) {
  promotionDrawerHourlyLoaded.value = false;
  promotionDrawerHourlyError.value = '';
  promotionDrawerHourlySourceRows.value = [];
  promotionDrawerPreviousHourlySourceRows.value = [];
  if (promotionDimension.value !== 'link' || !row?.linkId || !promotionFilters.start || !promotionFilters.end) return;
  const currentRange = { start: promotionFilters.start, end: promotionFilters.end };
  const previousRange = promotionComparisonRange.value;
  const requestKey = JSON.stringify({ linkId: row.linkId, storeName: row.storeName, currentRange, previousRange });
  promotionDrawerHourlyRequestKey.value = requestKey;
  promotionDrawerHourlyLoading.value = true;
  const params = (range) => ({
    link_id: row.linkId,
    product_id: row.linkId,
    product_name: row.title,
    store_name: row.storeName || '',
    start: range.start,
    end: range.end,
    size: 20000,
  });
  try {
    const [currentResponse, previousResponse] = await Promise.all([
      loadPromotionHourly(params(currentRange)),
      previousRange.start && previousRange.end ? loadPromotionHourly(params(previousRange)) : Promise.resolve({ success: true, data: [] }),
    ]);
    if (requestKey !== promotionDrawerHourlyRequestKey.value) return;
    if (!currentResponse?.success) throw new Error(currentResponse?.error || '当前周期推广日数据加载失败');
    if (!previousResponse?.success) throw new Error(previousResponse?.error || '对比周期推广日数据加载失败');
    promotionDrawerHourlySourceRows.value = currentResponse.data || [];
    promotionDrawerPreviousHourlySourceRows.value = previousResponse.data || [];
    promotionDrawerHourlyLoaded.value = true;
  } catch (err) {
    if (requestKey === promotionDrawerHourlyRequestKey.value) promotionDrawerHourlyError.value = err.message || '推广日数据加载失败';
  } finally {
    if (requestKey === promotionDrawerHourlyRequestKey.value) promotionDrawerHourlyLoading.value = false;
  }
}
function closePromotionDetails() { promotionExpandedKey.value = ''; promotionHourlySourceRows.value = []; promotionHourlyError.value = ''; }
function openPromotionImagePreview(imageUrl) { if (imageUrl) promotionImagePreviewUrl.value = imageUrl; }
function closePromotionImagePreview() { promotionImagePreviewUrl.value = ''; }
function formatPromotionMoney(value) { return `${Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`; }
function formatPromotionValue(value, column) {
  if (column.key === 'title') return String(value || '—');
  if (column.key === 'createdAt') return String(value || '—').slice(0, 19);
  if (column.tone === 'rate') return Number(value || 0).toFixed(2);
  if (column.tone === 'number') return Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 });
  return value || '—';
}
function changePromotionSort(key) {
  if (!promotionColumns.some((column) => column.key === key && column.sortable !== false)) return;
  promotionSort.order = promotionSort.key === key && promotionSort.order === 'asc' ? 'desc' : 'asc';
  promotionSort.key = key;
  promotionPage.value = 1;
}
function openPromotionColumnConfig() {
  promotionColumnDraft.value = [...promotionVisibleColumns.value];
  promotionColumnSearch.value = '';
  promotionDraggedColumn.value = '';
  promotionColumnsOpen.value = true;
}
function togglePromotionColumnDraft(key) {
  const current = promotionColumnDraft.value;
  promotionColumnDraft.value = current.includes(key) ? current.filter((item) => item !== key) : [...current, key];
}
function togglePromotionColumnGroup(group) {
  const groupKeys = group.keys;
  const allSelected = groupKeys.every((key) => promotionColumnDraft.value.includes(key));
  promotionColumnDraft.value = allSelected
    ? promotionColumnDraft.value.filter((key) => !groupKeys.includes(key))
    : [...promotionColumnDraft.value, ...groupKeys.filter((key) => !promotionColumnDraft.value.includes(key))];
}
function removePromotionColumn(key) {
  promotionColumnDraft.value = promotionColumnDraft.value.filter((item) => item !== key);
}
function movePromotionColumn(index, offset) {
  const nextIndex = index + offset;
  if (nextIndex < 0 || nextIndex >= promotionColumnDraft.value.length) return;
  const next = [...promotionColumnDraft.value];
  [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
  promotionColumnDraft.value = next;
}
function startPromotionColumnDrag(key) {
  promotionDraggedColumn.value = key;
}
function dropPromotionColumn(targetKey) {
  const sourceKey = promotionDraggedColumn.value;
  if (!sourceKey || sourceKey === targetKey) return;
  const next = [...promotionColumnDraft.value];
  const sourceIndex = next.indexOf(sourceKey);
  const targetIndex = next.indexOf(targetKey);
  if (sourceIndex < 0 || targetIndex < 0) return;
  next.splice(sourceIndex, 1);
  next.splice(next.indexOf(targetKey), 0, sourceKey);
  promotionColumnDraft.value = next;
  promotionDraggedColumn.value = '';
}
function restorePromotionColumns() {
  promotionColumnDraft.value = [...defaultPromotionVisibleColumns];
}
function cancelPromotionColumnConfig() {
  promotionColumnsOpen.value = false;
  promotionColumnDraft.value = [...promotionVisibleColumns.value];
  promotionColumnSearch.value = '';
  promotionDraggedColumn.value = '';
}
function applyPromotionColumnConfig() {
  if (!promotionColumnDraft.value.length) {
    promotionNotice('请至少选择一个字段');
    return;
  }
  promotionVisibleColumns.value = [...promotionColumnDraft.value];
  promotionColumnsOpen.value = false;
  promotionNotice('字段设置已应用');
}
function savePromotionColumnTemplate() {
  if (!promotionColumnDraft.value.length) {
    promotionNotice('请至少选择一个字段');
    return;
  }
  localStorage.setItem('link-monitor-promotion-columns-template', JSON.stringify(promotionColumnDraft.value));
  promotionNotice('字段模板已保存');
}
function promotionNotice(message) {
  promotionNoticeMessage.value = message;
  window.clearTimeout(promotionNoticeTimer.value);
  promotionNoticeTimer.value = window.setTimeout(() => { promotionNoticeMessage.value = ''; }, 2200);
}
function scrollPromotionKpis(direction) {
  promotionKpiTrack.value?.scrollBy({ left: direction * Math.max(260, promotionKpiTrack.value.clientWidth * 0.72), behavior: 'smooth' });
}
function goalNodeExpanded(key) { return expandedGoalNodes.value.has(key); }
function toggleGoalNode(key) { const next = new Set(expandedGoalNodes.value); if (next.has(key)) { next.delete(key); if (key === 'root') { next.delete('brand'); next.delete('person'); } } else next.add(key); expandedGoalNodes.value = next; }
function setRange(preset) { rangePreset.value = preset; const dates = availableDates.value; if (!dates.length) return; const end = dates.at(-1); if (preset === 'all') { dateStart.value = dates[0]; dateEnd.value = end; } else if (preset === 'month') { const month = end.slice(0, 7); const inMonth = dates.filter((date) => date.startsWith(month)); dateStart.value = inMonth[0]; dateEnd.value = inMonth.at(-1); } else { const days = preset === 'yesterday' ? 1 : preset === '3d' ? 3 : preset === '14d' ? 14 : preset === '30d' ? 30 : 7; dateStart.value = dates[Math.max(0, dates.length - days)]; dateEnd.value = end; } }
function creationParams() { if (creationFilter.mode === 'custom') return { creation_start: creationFilter.start, creation_end: creationFilter.end }; return { creation_days: Math.max(1, Number(creationFilter.days || 1)) }; }
function ordersFilterParams() {
  const rawOrders = String(globalFilters.orders ?? '').trim();
  // 输入框为空代表“不按单量筛选”；只有用户明确输入 0，才执行单量等于 0 的筛选。
  if (!rawOrders) return {};
  const orders = Number(rawOrders);
  if (!Number.isFinite(orders) || orders < 0) return {};
  return { orders_gte: orders, orders_lte: orders };
}
function globalCustomFilterJson() {
  return activeLinkPresetFilters.value.length ? JSON.stringify(activeLinkPresetFilters.value) : '';
}
function globalFilterParams() {
  return {
    ...creationParams(),
    ...ordersFilterParams(),
    link_ids: globalFilters.link_ids.trim(),
    product_code: globalFilters.product_code.trim(),
    product_name: globalFilters.product_name.trim(),
    brand: globalFilters.brand,
    sale_status: globalFilters.sale_status,
    store_name: globalFilters.store_name.trim(),
    store_person: globalFilters.store_person,
    filter_json: globalCustomFilterJson(),
  };
}
async function applyRange() { if (dateStart.value > dateEnd.value) [dateStart.value, dateEnd.value] = [dateEnd.value, dateStart.value]; if (creationFilter.mode === 'custom' && creationFilter.start && creationFilter.end && creationFilter.start > creationFilter.end) [creationFilter.start, creationFilter.end] = [creationFilter.end, creationFilter.start]; linkDataDateStart.value = dateStart.value; linkDataDateEnd.value = dateEnd.value; rangePreset.value = ''; await loadAll(globalFilterParams()); if (activeTab.value === 'promotion') await refreshPromotionLinkViews(); else await refreshLinkViews(); }
async function clearGlobalFilters() { Object.assign(globalFilters, { link_ids: '', product_code: '', product_name: '', orders: '', brand: '', store_name: '', store_person: '', sale_status: '' }); Object.assign(creationFilter, { mode: 'age', days: 30, start: '', end: '' }); activeLinkPresetId.value = ''; activeLinkPresetFilters.value = []; linkFilters.splice(0); expandedLinkSummaryId.value = ''; linkSummaryDailyRows.value = []; linkSummaryDailyError.value = ''; await applyRange(); }
function loadTargetForm() { const source = activeTarget.value || {}; targetForm.monthTarget = Number(source.monthTarget || 0); targetForm.profitRate = Number(source.profitRate || 0); targetForm.persons = { ...(source.persons || {}) }; targetForm.brands = { ...(source.brands || {}) }; }
async function saveCurrentTargets() { savingTargets.value = true; targetMessage.value = ''; try { await saveTargets(activeMonth.value, { monthTarget: targetForm.monthTarget || '', profitRate: targetForm.profitRate || '', persons: targetForm.persons, brands: targetForm.brands }); targetMessage.value = '已保存并同步到 API'; } catch (err) { targetMessage.value = err.message; } finally { savingTargets.value = false; } }
function createStandardFilterConfig(open = true) {
  return { pageSize: 20, visibleFields: null, filters: [], open, columnsOpen: false, previewRows: [], previewMeta: { total: 0, page: 1, pages: 0, size: 20 }, message: '', querying: false };
}
function normalizeStandardFilterConfig(source = {}, legacy = {}) {
  const raw = source && typeof source === 'object' ? source : {};
  const filters = Array.isArray(raw.filters) ? raw.filters.map((filter, index) => ({ id: filter.id || `standard-${Date.now()}-${index}`, field: filter.field || '', fieldSearch: '', op: filter.op || 'contains', v1: filter.v1 || '', v2: filter.v2 || '' })) : [];
  const addLegacyFilter = (field, value) => {
    if (value && !filters.some((filter) => filter.field === field)) filters.unshift({ id: `standard-legacy-${Date.now()}-${field}`, field, fieldSearch: '', op: 'contains', v1: value, v2: '' });
  };
  addLegacyFilter('链接id', raw.linkIds);
  addLegacyFilter('品牌', legacy.brand);
  addLegacyFilter('商品编码', legacy.productCode);
  addLegacyFilter('商品名称', legacy.productName);
  if ((raw.dateStart || raw.dateEnd) && !filters.some((filter) => filter.field === '链接创建时间')) filters.unshift({ id: `standard-legacy-${Date.now()}-creation`, field: '链接创建时间', fieldSearch: '', op: 'between', v1: raw.dateStart || '', v2: raw.dateEnd || '' });
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
  const activeFilters = [...activeLinkPresetFilters.value, ...activeLinkFilters.value];
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
    ...ordersFilterParams(),
    profit_rate_lte: linkQuery.profit_rate_lte,
    filter_json: activeFilters.length ? JSON.stringify(activeFilters) : '',
  });
  selectedLinks.value = [];
}
async function fetchLinkDashboard(page = 1) { await loadLinkDashboard({ page, size: linkQuery.size, start: dateStart.value, end: dateEnd.value, search: linkQuery.search, link_ids: globalFilters.link_ids, product_code: globalFilters.product_code, product_name: globalFilters.product_name, brand: globalFilters.brand, store_name: globalFilters.store_name, store_person: globalFilters.store_person, ...creationParams(), ...ordersFilterParams(), filter_json: globalCustomFilterJson() }); }
function changeLinkSummarySort(key) {
  const column = linkSummaryColumns.find((item) => item.key === key);
  if (!column) return;
  if (linkSummarySort.key === key) linkSummarySort.order = linkSummarySort.order === 'asc' ? 'desc' : 'asc';
  else { linkSummarySort.key = key; linkSummarySort.order = 'desc'; }
  fetchLinkSummary(1);
}
async function fetchLinkSummary(page = 1) { await loadLinkSummary({ page, size: linkSummaryQuery.size, start: dateStart.value, end: dateEnd.value, search: linkSummaryQuery.search, link_ids: globalFilters.link_ids, product_code: globalFilters.product_code, product_name: globalFilters.product_name, brand: globalFilters.brand, store_name: globalFilters.store_name, store_person: globalFilters.store_person, sort_by: linkSummarySort.key, sort_order: linkSummarySort.order, ...creationParams(), ...ordersFilterParams(), filter_json: globalCustomFilterJson() }); }
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
    const result = await queryLinks({ page: 1, size: 100, start: dateStart.value, end: dateEnd.value, link_ids: linkId, ...creationParams(), ...ordersFilterParams(), filter_json: globalCustomFilterJson() });
    linkSummaryDailyRows.value = result.data || [];
  } catch (err) {
    linkSummaryDailyError.value = err.message || '每日明细加载失败';
  } finally {
    linkSummaryDailyLoading.value = false;
  }
}
async function refreshLinkViews() { await Promise.all([fetchLinkDashboard(1), fetchLinks(1)]); }
async function refreshPromotionLinkViews() {
  // 推广页的统一表使用顶部全局数据日期，避免只刷新旧的利润汇总表。
  if (dateStart.value) promotionFilters.start = dateStart.value;
  if (dateEnd.value) promotionFilters.end = dateEnd.value;
  await Promise.all([rebuildPromotionRows(), fetchLinkSummary(1)]);
}
function refreshLinkData() { return fetchLinks(1); }
function scheduleLinkRefresh() { window.clearTimeout(linkRefreshTimer); linkRefreshTimer = window.setTimeout(refreshLinkViews, 240); }
function schedulePromotionLinkRefresh() { window.clearTimeout(linkRefreshTimer); linkRefreshTimer = window.setTimeout(refreshPromotionLinkViews, 240); }
function scheduleProductManagementRefresh() { window.clearTimeout(linkRefreshTimer); linkRefreshTimer = window.setTimeout(refreshLinkData, 240); }
function normalizeLinkDateRange() { if (dateStart.value > dateEnd.value) [dateStart.value, dateEnd.value] = [dateEnd.value, dateStart.value]; }
function normalizeLinkDataDateRange() { if (linkDataDateStart.value && linkDataDateEnd.value && linkDataDateStart.value > linkDataDateEnd.value) [linkDataDateStart.value, linkDataDateEnd.value] = [linkDataDateEnd.value, linkDataDateStart.value]; }
function toggleLinkAlert(key) { linkAlertOpen[key] = !linkAlertOpen[key]; }
function selectLinkAlert(item) { linkQuery.search = item.id; linkDetailExpanded.value = true; refreshPromotionLinkViews(); }
function linkFilterType(filter) { return linkColumnOptions.value.find((column) => column.key === filter.field)?.type || 'text'; }
function linkFilterInputType(filter) { return linkFilterType(filter) === 'date' ? 'date' : linkFilterType(filter) === 'number' ? 'number' : 'text'; }
function linkFilterPlaceholder(filter) { return filter.field === '链接id' ? '支持逗号分隔多个链接 ID' : linkFilterType(filter) === 'text' ? '包含值' : '值'; }
function linkFilterUsesSecondValue(filter) { return linkFilterType(filter) !== 'text' && filter.op === 'between'; }
function onLinkFilterFieldChange(filter) { filter.op = linkFilterType(filter) === 'text' ? 'contains' : 'between'; filter.v1 = ''; filter.v2 = ''; }
function normalizeLinkFilterOperator(filter) { const type = linkFilterType(filter); if (type === 'text' && !['contains', 'eq', 'equals'].includes(filter.op)) filter.op = 'contains'; if (type !== 'text' && !['between', 'eq', 'equals', 'gte', 'lte'].includes(filter.op)) filter.op = 'between'; if (filter.op !== 'between') filter.v2 = ''; }
function addLinkFilter() { linkFilters.push({ id: ++linkFilterId, field: '', op: 'contains', v1: '', v2: '' }); }
function removeLinkFilter(index) { linkFilters.splice(index, 1); applyLinkFilters(); }
const activeLinkFilters = computed(() => linkFilters.filter((filter) => filter.field && (filter.v1 || filter.v2)).map(({ field, op, v1, v2 }) => ({ field, op, v1, v2 })));
const linkFilterSummary = computed(() => activeLinkFilters.value.map((filter) => {
  const label = linkColumnOptions.value.find((column) => column.key === filter.field)?.label || filter.field;
  const text = filter.op === 'between' ? `${filter.v1} ~ ${filter.v2}` : filter.op === 'gte' ? `≥ ${filter.v1}` : filter.op === 'lte' ? `≤ ${filter.v1}` : filter.op === 'eq' || filter.op === 'equals' ? `= ${filter.v1}` : `包含 ${filter.v1}`;
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
function standardFilterFieldOptions(filter) {
  const query = String(filter.fieldSearch || '').trim().toLowerCase();
  const selected = linkColumnOptions.value.find((field) => field.key === filter.field);
  const options = query ? linkColumnOptions.value.filter((field) => `${field.label} ${field.key}`.toLowerCase().includes(query)) : linkColumnOptions.value;
  if (selected && !options.some((field) => field.key === selected.key)) return [selected, ...options];
  return options;
}
function standardFilterType(row, filter) { return linkColumnOptions.value.find((column) => column.key === filter.field)?.type || 'text'; }
function standardFilterInputType(row, filter) { const type = standardFilterType(row, filter); return type === 'date' ? 'date' : type === 'number' ? 'number' : 'text'; }
function standardFilterPlaceholder(row, filter) { return filter.field === '链接id' ? '支持逗号分隔多个链接 ID' : standardFilterType(row, filter) === 'text' ? '包含值' : '值'; }
function standardFilterUsesSecondValue(row, filter) { return standardFilterType(row, filter) !== 'text' && filter.op === 'between'; }
function onStandardFilterFieldChange(row, filter) { filter.fieldSearch = ''; filter.op = standardFilterType(row, filter) === 'text' ? 'contains' : 'between'; filter.v1 = ''; filter.v2 = ''; }
function normalizeStandardFilterOperator(row, filter) { const type = standardFilterType(row, filter); if (type === 'text' && !['contains', 'eq', 'equals'].includes(filter.op)) filter.op = 'contains'; if (type !== 'text' && !['between', 'eq', 'equals', 'gte', 'lte'].includes(filter.op)) filter.op = 'between'; if (filter.op !== 'between') filter.v2 = ''; }
function addStandardFilter(row) { row.filterConfig.filters.push({ id: `standard-filter-${++standardFilterId}`, field: '', fieldSearch: '', op: 'contains', v1: '', v2: '' }); }
function removeStandardFilter(row, index) { row.filterConfig.filters.splice(index, 1); }
function toggleStandardColumn(row, key, checked) { const allKeys = linkColumnOptions.value.map((column) => column.key); const selected = row.filterConfig.visibleFields === null ? [...allKeys] : [...row.filterConfig.visibleFields]; if (checked && !selected.includes(key)) selected.push(key); if (!checked) { const index = selected.indexOf(key); if (index >= 0) selected.splice(index, 1); } row.filterConfig.visibleFields = selected.length === allKeys.length ? null : selected; }
function selectAllStandardColumns(row, checked) { row.filterConfig.visibleFields = checked ? null : []; }
function standardActiveFilters(row) {
  return (row.filterConfig.filters || []).filter((filter) => filter.field && (filter.v1 || filter.v2)).map(({ field, op, v1, v2 }) => ({ field, op, v1, v2 }));
}
function standardFilterSummary(row) { return standardActiveFilters(row).map((filter) => { const label = linkColumnOptions.value.find((column) => column.key === filter.field)?.label || filter.field; const text = filter.op === 'between' ? `${filter.v1} ~ ${filter.v2}` : filter.op === 'gte' ? `≥ ${filter.v1}` : filter.op === 'lte' ? `≤ ${filter.v1}` : filter.op === 'eq' || filter.op === 'equals' ? `= ${filter.v1}` : `包含 ${filter.v1}`; return `${label} ${text}`; }).join(' AND '); }
function standardFilterParams(row) {
  const config = row.filterConfig;
  return { page: 1, size: Number(config.pageSize || 20), start: dateStart.value, end: dateEnd.value, link_ids: globalFilters.link_ids || '', product_code: globalFilters.product_code || '', product_name: globalFilters.product_name || '', brand: globalFilters.brand || '', store_name: globalFilters.store_name || '', store_person: globalFilters.store_person || '', ...creationParams(), ...ordersFilterParams(), filter_json: JSON.stringify(standardActiveFilters(row)), aggregate: 'link_person' };
}
async function queryStandardRow(row) { const config = row.filterConfig; config.querying = true; config.message = ''; try { const result = await queryLinks(standardFilterParams(row)); config.previewRows = result.data || []; config.previewMeta = { total: result.total || 0, page: result.page || 1, pages: result.pages || 0, size: result.size || config.pageSize }; config.message = `匹配 ${Number(result.total || 0).toLocaleString()} 组`; } catch (err) { config.previewRows = []; config.previewMeta = { total: 0, page: 1, pages: 0, size: config.pageSize }; config.message = err.message || '查询失败'; } finally { config.querying = false; } }
function exportStandardRow(row) { const config = row.filterConfig; if (!config.previewRows.length) return; const selected = config.visibleFields === null ? linkColumnOptions.value : linkColumnOptions.value.filter((column) => config.visibleFields.includes(column.key)); if (!selected.length) return; const escape = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`; const header = selected.map((column) => escape(column.label)).join(','); const rows = config.previewRows.map((item) => selected.map((column) => escape(formatLinkValue(item[column.key], column.key, item))).join(',')); const blob = new Blob([`\uFEFF${[header, ...rows].join('\n')}`], { type: 'text/csv;charset=utf-8' }); const anchor = document.createElement('a'); anchor.href = URL.createObjectURL(blob); anchor.download = `link_setting_${row.id || 'draft'}_${new Date().toISOString().slice(0, 10)}.csv`; anchor.click(); URL.revokeObjectURL(anchor.href); }
const operationTaskStatusLabels = Object.freeze({ pending: '排队中', running: '执行中', cancelling: '中断中', completed: '已完成', failed: '失败', cancelled: '已取消' });
function operationTaskStatusLabel(status) { return operationTaskStatusLabels[status] || status || '未知'; }
function operationTaskStatusTone(status) { return `is-${status || 'unknown'}`; }
function operationTaskCanCancel(task) { return ['pending', 'running'].includes(task?.status); }
function formatOperationDateTime(value) {
  if (!value) return '—';
  return String(value).replace('T', ' ').slice(0, 19);
}
function operationTaskQueueHint(task) {
  if (task?.status === 'running') return '当前执行';
  if (task?.status === 'cancelling') return '等待执行端确认';
  if (task?.status === 'pending' && task?.scheduled_at) return `计划于 ${formatOperationDateTime(task.scheduled_at)} 执行`;
  return task?.queue_position ? `排队第 ${task.queue_position} 位` : '等待排队';
}
function formatOperationStores(task) {
  const stores = [...new Set((Array.isArray(task?.store_names) ? task.store_names : []).filter(Boolean))];
  if (!stores.length) return '未识别店铺';
  return stores.length > 2 ? `${stores.slice(0, 2).join('、')} 等 ${stores.length} 家` : stores.join('、');
}
async function loadOperationQueueNow() {
  if (operationQueueLoading.value) return;
  operationQueueLoading.value = true;
  operationQueueError.value = '';
  try {
    const response = await fetchOperationQueue();
    operationQueue.value = {
      tasks: response.tasks || [],
      history: response.history || [],
      summary: { pending: 0, running: 0, cancelling: 0, completed: 0, failed: 0, cancelled: 0, ...(response.summary || {}) },
    };
  } catch (err) {
    operationQueueError.value = err.message || '任务队列加载失败';
  } finally {
    operationQueueLoading.value = false;
  }
}
async function interruptOperationTask(task) {
  if (!operationTaskCanCancel(task)) return;
  operationCancellingId.value = task.id;
  operationQueueError.value = '';
  try {
    await cancelOperationTask(task.id);
    await loadOperationQueueNow();
  } catch (err) {
    operationQueueError.value = err.message || '任务中断失败';
  } finally {
    operationCancellingId.value = '';
    operationInterruptConfirmId.value = '';
  }
}
function stopOperationQueuePolling() {
  if (operationQueueTimer) window.clearInterval(operationQueueTimer);
  operationQueueTimer = null;
}
function startOperationQueuePolling() {
  stopOperationQueuePolling();
  loadOperationQueueNow();
  operationQueueTimer = window.setInterval(() => {
    if (activeTab.value === 'admin') loadOperationQueueNow();
  }, 5000);
}
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
async function submitSelectedLinks() {
  const linkIds = [...delistOperationIds.value];
  if (!linkIds.length) return;
  const schedule = resolveOperationSchedule(delistScheduleMode.value, delistScheduledAt.value);
  if (schedule.error) {
    delistMessage.value = schedule.error;
    return;
  }
  delisting.value = true;
  delistMessage.value = '';
  try {
    const response = await submitDelist({
      task_type: 'delist',
      operation: 'delist',
      operation_type: 'delist',
      operation_name: '产品下架',
      operation_label: '产品下架',
      link_ids: linkIds,
      store_names: [...new Set(selectedDelistLinkRows.value.map((item) => item.storeName).filter(Boolean))],
      ...schedule.payload,
      operator: '链接监控',
    });
    if (!response?.success) throw new Error(response?.error || '产品下架提交失败');
    delistConfirmOpen.value = false;
    await loadOperationQueueNow();
    window.alert(schedule.payload.schedule_mode === 'scheduled' ? `已安排 ${linkIds.length} 条下架任务于 ${schedule.displayTime} 执行` : `已提交 ${linkIds.length} 条下架任务`);
    selectedPromotionIds.value = [];
    selectedLinks.value = [];
    delistTargetIds.value = [];
  } catch (err) {
    delistMessage.value = err.message || '产品下架提交失败';
  } finally {
    delisting.value = false;
  }
}
function openDelistConfirm() {
  if (!selectedOperationIds.value.length) return;
  delistTargetIds.value = [];
  delistScheduleMode.value = 'immediate';
  delistScheduledAt.value = '';
  delistMessage.value = '';
  delistConfirmOpen.value = true;
}
function openRowDelistConfirm(row) {
  if (!row?.linkId) return;
  delistTargetIds.value = [String(row.linkId)];
  delistScheduleMode.value = 'immediate';
  delistScheduledAt.value = '';
  delistMessage.value = '';
  delistConfirmOpen.value = true;
}
function closeDelistConfirm() {
  if (!delisting.value) {
    delistConfirmOpen.value = false;
    delistMessage.value = '';
    delistTargetIds.value = [];
  }
}
const selectedLinkRows = computed(() => selectedOperationIds.value.map((linkId) => {
  const promotionRow = promotionRows.value.find((item) => String(item.linkId) === String(linkId));
  const linkRow = links.value.find((item) => String(item['链接id']) === String(linkId));
  return { linkId, storeName: promotionRow?.storeName || linkRow?.['店铺名称'] || '' };
}));
const promotionAdjustOperationIds = computed(() => promotionAdjustTargetIds.value.length ? promotionAdjustTargetIds.value : selectedOperationIds.value);
const selectedAdjustLinkRows = computed(() => promotionAdjustOperationIds.value.map((linkId) => {
  const promotionRow = promotionRows.value.find((item) => String(item.linkId) === String(linkId));
  const linkRow = links.value.find((item) => String(item['链接id']) === String(linkId));
  return { linkId, storeName: promotionRow?.storeName || linkRow?.['店铺名称'] || '' };
}));
const delistOperationIds = computed(() => delistTargetIds.value.length ? delistTargetIds.value : selectedOperationIds.value);
const selectedDelistLinkRows = computed(() => delistOperationIds.value.map((linkId) => {
  const promotionRow = promotionRows.value.find((item) => String(item.linkId) === String(linkId));
  const linkRow = links.value.find((item) => String(item['链接id']) === String(linkId));
  return { linkId, storeName: promotionRow?.storeName || linkRow?.['店铺名称'] || '' };
}));
function openPromotionAdjust() {
  if (!selectedOperationIds.value.length) return;
  promotionAdjustTargetIds.value = [...selectedOperationIds.value];
  adjustPreset.value = 0.05;
  adjustScheduleMode.value = 'immediate';
  adjustScheduledAt.value = '';
  adjustMessage.value = '';
  adjustModalOpen.value = true;
}
function openRowPromotionAdjust(row) {
  if (!row?.linkId) return;
  promotionAdjustTargetIds.value = [String(row.linkId)];
  adjustPreset.value = 0.05;
  adjustScheduleMode.value = 'immediate';
  adjustScheduledAt.value = '';
  adjustMessage.value = '';
  adjustModalOpen.value = true;
}
function closePromotionAdjust() {
  if (!adjustingPromotion.value) {
    adjustModalOpen.value = false;
    promotionAdjustTargetIds.value = [];
  }
}
function resolveOperationSchedule(mode, value) {
  if (mode !== 'scheduled') return { payload: { schedule_mode: 'immediate', scheduled_at: null }, displayTime: '' };
  if (!value) return { error: '请选择定时执行时间' };
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return { error: '定时执行时间格式不正确' };
  if (parsed.getTime() <= Date.now()) return { error: '定时执行时间必须晚于当前时间' };
  // datetime-local 没有时区；提交浏览器当前时区偏移，服务器可将它换算成本地执行时间。
  const offsetMinutes = -parsed.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? '+' : '-';
  const absoluteOffset = Math.abs(offsetMinutes);
  const offset = `${sign}${String(Math.floor(absoluteOffset / 60)).padStart(2, '0')}:${String(absoluteOffset % 60).padStart(2, '0')}`;
  return { payload: { schedule_mode: 'scheduled', scheduled_at: `${value}:00${offset}` }, displayTime: value.replace('T', ' ') };
}
async function submitPromotionAdjust() {
  const preset = promotionAdjustPresets.find((item) => item.value === adjustPreset.value);
  if (!preset) {
    adjustMessage.value = '请选择投产调整档次';
    return;
  }
  const value = preset.value;
  const linkIds = [...promotionAdjustOperationIds.value];
  if (!linkIds.length) {
    adjustMessage.value = '请至少选择一条链接';
    return;
  }
  const schedule = resolveOperationSchedule(adjustScheduleMode.value, adjustScheduledAt.value);
  if (schedule.error) {
    adjustMessage.value = schedule.error;
    return;
  }
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
      link_ids: linkIds,
      store_names: selectedAdjustLinkRows.value.map((item) => item.storeName),
      ...schedule.payload,
      direction: 'up',
      value,
      operator: '链接监控',
    });
    if (!response?.success) throw new Error(response?.error || '调整投产提交失败');
    adjustModalOpen.value = false;
    await loadOperationQueueNow();
    window.alert(schedule.payload.schedule_mode === 'scheduled' ? `已安排 ${linkIds.length} 条调整投产任务于 ${schedule.displayTime} 执行` : `已提交 ${linkIds.length} 条调整投产任务`);
    selectedPromotionIds.value = [];
    selectedLinks.value = [];
    promotionAdjustTargetIds.value = [];
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
  if (activeTab.value === 'promotion' && dateStart.value && dateEnd.value) schedulePromotionLinkRefresh();
  if (activeTab.value === 'product-management' && dateStart.value && dateEnd.value) scheduleProductManagementRefresh();
});
watch([availableDates], () => {
  if (!promotionFilters.start && availableDates.value.length) {
    const [start, end] = promotionDateBounds(30);
    promotionFilters.start = start;
    promotionFilters.end = end;
  }
  if (activeTab.value === 'promotion' || !promotionRows.value.length) rebuildPromotionRows();
}, { deep: true });
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
watch(activeTab, (tab) => {
  if (tab === 'admin') startOperationQueuePolling();
  else stopOperationQueuePolling();
});
onBeforeUnmount(stopOperationQueuePolling);
onMounted(async () => {
  try {
    const savedColumns = JSON.parse(localStorage.getItem('link-monitor-promotion-columns-template') || 'null');
    if (Array.isArray(savedColumns) && savedColumns.length) promotionVisibleColumns.value = savedColumns.filter((key) => promotionColumns.some((column) => column.key === key));
  } catch { /* 忽略损坏的本地字段模板，继续使用默认配置 */ }
  await loadAll(globalFilterParams());
  await refreshPromotionLinkViews();
});
</script>
