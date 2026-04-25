(function () {
  const data = window.APP_DATA || {};
  const app = document.getElementById('app');

  if (!app) return;

  const state = {
    activeTab: (data.tabs && data.tabs[0]) || 'AI工具',
    search: '',
    activeAnnouncement:
      (data.announcement && data.announcement.sections && data.announcement.sections[0] && data.announcement.sections[0].id) ||
      'knowledgePlanet',
    selectedCategoryByTab: {
      AI工具: '全部',
      软件测试工具: '全部',
      OpenClaw: '全部'
    }
  };
  let searchRenderTimer = null;

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function getDomain(url) {
    try {
      return new URL(url).hostname.replace(/^www\./, '');
    } catch (error) {
      const match = String(url || '').match(/(?:https?:\/\/)?(?:www\.)?([^/]+)/i);
      return match ? match[1] : String(url || '');
    }
  }

  function sanitizeHttpUrl(url) {
    const raw = String(url || '').trim();
    if (!raw) return '';
    try {
      const parsed = new URL(raw, window.location.href);
      if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
        return parsed.href;
      }
    } catch (error) {
      return '';
    }
    return '';
  }

  function faviconUrl(url) {
    return `https://www.google.com/s2/favicons?sz=64&domain_url=${encodeURIComponent(url || '')}`;
  }

  function getTabPayload(tab) {
    if (tab === 'AI工具') return { items: data.aiTools || [], categories: data.aiCategories || [] };
    if (tab === 'Prompt') return { items: data.prompts || [], categories: [] };
    if (tab === 'Skill') return { items: data.skills || [], categories: [] };
    if (tab === 'MCP') return { items: data.mcps || [], categories: [] };
    if (tab === 'OpenClaw') return { items: data.openClaw || [], categories: data.openClawCategories || [] };
    if (tab === '软件测试工具') return { items: data.testTools || [], categories: data.testCategories || [] };
    if (tab === '软件测试学习网站') return { items: data.learningSites || [], categories: [] };
    return { items: [], categories: [] };
  }

  function filterItems(items, search, category) {
    const keyword = search.trim().toLowerCase();
    return items.filter((item) => {
      if (category && category !== '全部' && item.category !== category) return false;
      if (!keyword) return true;
      const text = `${item.name || ''} ${item.description || ''} ${(item.tags || []).join(' ')} ${item.category || ''}`.toLowerCase();
      return text.includes(keyword);
    });
  }

  function categoryCountMap(items, categories) {
    const map = { 全部: items.length };
    categories.forEach((category) => (map[category] = 0));
    items.forEach((item) => {
      const category = item.category;
      if (Object.prototype.hasOwnProperty.call(map, category)) {
        map[category] += 1;
      }
    });
    return map;
  }

  function renderTabs() {
    const tabs = data.tabs || [];
    return `
      <div class="tab-bar">
        ${tabs
          .map(
            (tab) => `
          <button class="tab-btn ${tab === state.activeTab ? 'active' : ''}" data-tab="${escapeHtml(tab)}">${escapeHtml(tab)}</button>
        `
          )
          .join('')}
      </div>
    `;
  }

  function renderCategorySidebar(categories, countMap) {
    const selected = state.selectedCategoryByTab[state.activeTab] || '全部';
    return `
      <aside class="sidebar">
        <p class="side-title">快速筛选</p>
        <div class="side-list">
          <button class="side-item ${selected === '全部' ? 'active' : ''}" data-category="全部">全部 (${countMap['全部'] || 0})</button>
          ${categories
            .map(
              (category) => `
              <button class="side-item ${selected === category ? 'active' : ''}" data-category="${escapeHtml(category)}">
                ${escapeHtml(category)} (${countMap[category] || 0})
              </button>
            `
            )
            .join('')}
        </div>
      </aside>
    `;
  }

  function renderAnnouncementSidebar() {
    const sections = (data.announcement && data.announcement.sections) || [];
    return `
      <aside class="sidebar">
        <p class="side-title">公告菜单</p>
        <div class="side-list">
          ${sections
            .map(
              (section) => `
              <button class="side-item ${state.activeAnnouncement === section.id ? 'active' : ''}" data-ann="${escapeHtml(section.id)}">
                ${escapeHtml(section.label)}
              </button>
            `
            )
            .join('')}
        </div>
      </aside>
    `;
  }

  function renderSearchAndCategories(categories, countMap) {
    const selected = state.selectedCategoryByTab[state.activeTab] || '全部';
    return `
      <div class="filters">
        <div class="search-wrap">
          <input
            class="search-input"
            data-search-input
            value="${escapeHtml(state.search)}"
            placeholder="搜索名称、描述或标签"
          />
          ${
            state.search
              ? '<button class="search-clear" type="button" data-clear aria-label="清除搜索">×</button>'
              : ''
          }
        </div>
        ${
          categories.length
            ? `<div class="category-row">
                <button class="category-chip ${selected === '全部' ? 'active' : ''}" data-category="全部">全部 (${countMap['全部'] || 0})</button>
                ${categories
                  .map(
                    (category) => `
                  <button class="category-chip ${selected === category ? 'active' : ''}" data-category="${escapeHtml(category)}">
                    ${escapeHtml(category)} (${countMap[category] || 0})
                  </button>
                `
                  )
                  .join('')}
              </div>`
            : ''
        }
      </div>
    `;
  }

  function renderCard(item, index) {
    const rawUrl = item.url || '';
    const safeUrl = sanitizeHttpUrl(rawUrl);
    const name = escapeHtml(item.name || '未命名');
    const desc = escapeHtml(item.description || '暂无描述');
    const url = escapeHtml(safeUrl);
    const domain = escapeHtml(getDomain(safeUrl || rawUrl || ''));
    const category = item.category ? `<span class="category-badge">${escapeHtml(item.category)}</span>` : '<span></span>';
    const tags = (item.tags || []).slice(0, 4);
    const firstLetter = escapeHtml(String(item.name || '?').trim().charAt(0) || '?');

    return `
      <article class="card" data-open-url="${url}" style="--delay:${Math.min(index, 16) * 35}ms">
        <div class="card-top">
          <img class="logo" src="${faviconUrl(safeUrl)}" alt="" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='grid';" />
          <span class="logo-fallback" style="display:none">${firstLetter}</span>
          <div>
            <h3 class="card-title">${name}</h3>
            <p class="card-domain">${domain}</p>
          </div>
        </div>
        <p class="card-desc">${desc}</p>
        ${
          tags.length
            ? `<div class="tag-row">${tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}</div>`
            : ''
        }
        <div class="card-foot">
          ${category}
          <span class="open-hint">打开站点</span>
        </div>
      </article>
    `;
  }

  function renderToolPanel(payload, countMap) {
    const categories = payload.categories;
    const selectedCategory = state.selectedCategoryByTab[state.activeTab] || '全部';
    const filtered = filterItems(payload.items, state.search, selectedCategory);

    return `
      <section class="main-panel">
        <div class="toolboard">
          ${renderSearchAndCategories(categories, countMap)}
          <div class="meta-row">
            <span>当前栏目：${escapeHtml(state.activeTab)}</span>
            <span>结果：${filtered.length} / ${payload.items.length}</span>
          </div>
          ${
            filtered.length
              ? `<div class="grid">${filtered.map((item, index) => renderCard(item, index)).join('')}</div>`
              : '<div class="empty">没有匹配项，试试更短关键词或切换分类。</div>'
          }
        </div>
      </section>
    `;
  }

  function renderAnnouncementPanel() {
    const sections = (data.announcement && data.announcement.sections) || [];
    const current = sections.find((section) => section.id === state.activeAnnouncement) || sections[0];

    if (!current) {
      return '<section class="main-panel"><div class="announcement">暂无公告内容。</div></section>';
    }

    return `
      <section class="main-panel">
        <article class="announcement">
          <h2>${escapeHtml(current.title)}</h2>
          <p>${escapeHtml(current.intro)}</p>
          <ul>
            ${(current.bullets || []).map((line) => `<li>${escapeHtml(line)}</li>`).join('')}
          </ul>
          <div class="announcement-footer">${escapeHtml(current.footer || '')}</div>
        </article>
      </section>
    `;
  }

  function render(options) {
    const preserveSearchFocus = options && options.preserveSearchFocus;
    const caretPos = preserveSearchFocus ? state.search.length : 0;
    const isAnnouncement = state.activeTab === '公告';
    const payload = getTabPayload(state.activeTab);
    const countMap = payload.categories.length ? categoryCountMap(payload.items, payload.categories) : { 全部: payload.items.length };
    const hasCategorySidebar = !isAnnouncement && payload.categories.length > 0;
    const shellClass = hasCategorySidebar || isAnnouncement ? 'content-shell' : 'content-shell single';

    app.innerHTML = `
      <header class="hero">
        <h1>${escapeHtml((data.siteMeta && data.siteMeta.title) || '资源导航')}</h1>
        <p>${escapeHtml((data.siteMeta && data.siteMeta.subtitle) || '')}</p>
      </header>
      ${renderTabs()}
      <section class="${shellClass}">
        ${
          isAnnouncement
            ? renderAnnouncementSidebar()
            : hasCategorySidebar
            ? renderCategorySidebar(payload.categories, countMap)
            : ''
        }
        ${isAnnouncement ? renderAnnouncementPanel() : renderToolPanel(payload, countMap)}
      </section>
    `;

    if (preserveSearchFocus) {
      const input = app.querySelector('[data-search-input]');
      if (input) {
        input.focus();
        try {
          input.setSelectionRange(caretPos, caretPos);
        } catch (error) {
          // ignore unsupported input APIs
        }
      }
    }
  }

  function cancelScheduledSearchRender() {
    if (searchRenderTimer) {
      window.clearTimeout(searchRenderTimer);
      searchRenderTimer = null;
    }
  }

  app.addEventListener('click', (event) => {
    const tabBtn = event.target.closest('[data-tab]');
    if (tabBtn) {
      cancelScheduledSearchRender();
      const nextTab = tabBtn.getAttribute('data-tab');
      state.activeTab = nextTab;
      state.search = '';
      render();
      return;
    }

    const categoryBtn = event.target.closest('[data-category]');
    if (categoryBtn) {
      cancelScheduledSearchRender();
      state.selectedCategoryByTab[state.activeTab] = categoryBtn.getAttribute('data-category') || '全部';
      render();
      return;
    }

    const annBtn = event.target.closest('[data-ann]');
    if (annBtn) {
      cancelScheduledSearchRender();
      state.activeAnnouncement = annBtn.getAttribute('data-ann') || state.activeAnnouncement;
      render();
      return;
    }

    const clearBtn = event.target.closest('[data-clear]');
    if (clearBtn) {
      cancelScheduledSearchRender();
      state.search = '';
      render();
      return;
    }

    const card = event.target.closest('[data-open-url]');
    if (card) {
      const url = sanitizeHttpUrl(card.getAttribute('data-open-url'));
      if (url) {
        window.open(url, '_blank', 'noopener');
      }
    }
  });

  app.addEventListener('input', (event) => {
    const input = event.target;
    if (!input.matches('[data-search-input]')) return;
    state.search = input.value || '';
    cancelScheduledSearchRender();
    searchRenderTimer = window.setTimeout(() => {
      searchRenderTimer = null;
      render({ preserveSearchFocus: true });
    }, 120);
  });

  render();
})();
