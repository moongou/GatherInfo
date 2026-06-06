import { useEffect, useState, useCallback } from "react";
import { Search, ExternalLink, Filter, X, BookOpen, BookOpenText } from "lucide-react";
import { fetchItems, fetchTags, fetchSources, fetchTopics } from "../api";
import type { CollectedItem, ItemList, Tag, Source, Topic } from "../types";

const PAGE_SIZE = 40;

export function ItemsPage() {
  const [data, setData] = useState<ItemList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [filterTag, setFilterTag] = useState("");
  const [filterSource, setFilterSource] = useState("");
  const [filterTopic, setFilterTopic] = useState("");
  const [filterCat, setFilterCat] = useState("");
  const [readingItem, setReadingItem] = useState<CollectedItem | null>(null);

  const [tags, setTags] = useState<Tag[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);

  useEffect(() => {
    fetchTags(undefined, 200).then(setTags).catch(() => {});
    fetchSources().then(setSources).catch(() => {});
    fetchTopics().then(setTopics).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await fetchItems({
        page, page_size: PAGE_SIZE,
        ...(query ? { q: query } : {}),
        ...(filterTag ? { tag: filterTag } : {}),
        ...(filterSource ? { source_id: filterSource } : {}),
        ...(filterTopic ? { topic_id: filterTopic } : {}),
        ...(filterCat ? { category: filterCat } : {}),
      });
      setData(result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
    setLoading(false);
  }, [page, query, filterTag, filterSource, filterTopic, filterCat]);

  useEffect(() => { void load(); }, [load]);

  // Listen for reading events from item cards
  useEffect(() => {
    const handler = (e: Event) => {
      const evt = e as CustomEvent;
      if (evt.detail) setReadingItem(evt.detail);
    };
    window.addEventListener('open-reading', handler);
    return () => window.removeEventListener('open-reading', handler);
  }, []);

  // Lock body scroll when reading modal is open
  useEffect(() => {
    if (readingItem) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [readingItem]);

  const clearFilters = () => {
    setQuery(""); setFilterTag(""); setFilterSource(""); setFilterTopic(""); setFilterCat("");
    setPage(1);
  };

  const hasFilters = query || filterTag || filterSource || filterTopic || filterCat;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>采集条目</h2>
          <p className="text-muted">
            {data ? `共 ${data.total.toLocaleString()} 条 · 第 ${data.page} 页` : "加载中..."}
          </p>
        </div>
      </div>

      {/* Search bar */}
      <div className="search-bar">
        <div className="search-input-wrapper">
          <Search size={14} className="search-icon" />
          <input
            value={query}
            onChange={(e) => { setQuery(e.target.value); setPage(1); }}
            placeholder="搜索标题或内容..."
            className="search-input"
          />
          {query && (
            <button type="button" className="btn-icon" onClick={() => { setQuery(""); setPage(1); }}>
              <X size={14} />
            </button>
          )}
        </div>

        <select value={filterTopic} onChange={(e) => { setFilterTopic(e.target.value); setPage(1); }}>
          <option value="">全部主题</option>
          {topics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>

        <select value={filterSource} onChange={(e) => { setFilterSource(e.target.value); setPage(1); }}>
          <option value="">全部信息源</option>
          {sources.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>

        <select value={filterTag} onChange={(e) => { setFilterTag(e.target.value); setPage(1); }}>
          <option value="">全部标签</option>
          {tags.slice(0, 50).map((t) => <option key={t.id} value={t.id}>{t.id} ({t.item_count})</option>)}
        </select>

        {hasFilters && (
          <button type="button" className="btn btn-sm btn-ghost" onClick={clearFilters}>
            <Filter size={12} /> 清除过滤
          </button>
        )}
      </div>

      {/* Item list */}
      {loading ? <div className="loading">加载条目...</div> :
       error ? <div className="error-banner">{error}</div> :
       !data ? null : (
        <>
          <div className="item-list">
            {data.items.map((item) => (
              <ItemCard key={item.id} item={item} />
            ))}
          </div>

          {/* Pagination */}
          <div className="pagination">
            <button type="button" className="btn btn-sm btn-ghost" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              上一页
            </button>
            <span className="text-muted">
              {data.page} / {Math.ceil(data.total / PAGE_SIZE) || 1}
            </span>
            <button type="button" className="btn btn-sm btn-ghost" disabled={data.items.length < PAGE_SIZE} onClick={() => setPage(page + 1)}>
              下一页
            </button>
          </div>
        </>
      )}
      {/* Reading Modal */}
      {readingItem && (
        <div className="modal-overlay" onClick={() => setReadingItem(null)}>
          <div className="modal reading-modal" onClick={(e) => e.stopPropagation()}>
            <div className="reading-modal-header">
              <div>
                <h3 style={{ fontSize: "1.1rem", fontWeight: 700, lineHeight: 1.4 }}>{readingItem.title}</h3>
                <div className="reading-modal-meta" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
                  {readingItem.source_id && <span className="chip">来源: {sources.find(s => s.id === readingItem.source_id)?.name || readingItem.source_id}</span>}
                  {readingItem.language && <span className="chip">{readingItem.language}</span>}
                  {readingItem.category && <span className="chip chip--blue">{readingItem.category}</span>}
                  {readingItem.published_at && <span className="text-muted small">发布: {new Date(readingItem.published_at).toLocaleString("zh")}</span>}
                  {readingItem.collected_at && <span className="text-muted small">采集: {new Date(readingItem.collected_at).toLocaleString("zh")}</span>}
                  {readingItem.tags?.map((t) => (
                    <span key={t.id} className="chip chip--pink" title={`${t.namespace}:${t.value}`}>{t.value}</span>
                  ))}
                </div>
              </div>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setReadingItem(null)}>
                <X size={16} />
              </button>
            </div>

            <div className="reading-modal-body">
              {/* Summary */}
              {readingItem.summary && (
                <div className="reading-summary">
                  <strong>摘要</strong>
                  <p>{readingItem.summary}</p>
                </div>
              )}

              {/* Full content */}
              {readingItem.url && (
                <div className="reading-url">
                  <strong>原文链接</strong>
                  <a href={readingItem.url} target="_blank" rel="noopener noreferrer">
                    {readingItem.url} <ExternalLink size={12} />
                  </a>
                </div>
              )}

              <div className="reading-content">
                {(readingItem as any).content ? (
                  <div style={{ whiteSpace: "pre-wrap", fontSize: "0.9rem", lineHeight: 1.8 }}>
                    {(readingItem as any).content}
                  </div>
                ) : (
                  <p className="text-muted" style={{ fontStyle: "italic", padding: 20, textAlign: "center" }}>
                    暂无详细内容，当前仅显示摘要信息。
                  </p>
                )}
              </div>

              <div className="reading-modal-footer">
                <div className="text-muted small">
                  质量评分: {readingItem.quality_score.toFixed(2)} | 
                  相关性: {readingItem.relevance_score.toFixed(2)} | 
                  状态: {readingItem.status}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

// ── Item card ────────────────────────────────────────────────────────────────

function ItemCard({ item }: { item: CollectedItem }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <article className="item-card">
      <div className="item-card-header">
        <h4 className="item-title" onClick={() => setExpanded(!expanded)}>
          {item.title}
        </h4>
        <div className="item-card-meta">
          {item.url && (
            <a href={item.url} target="_blank" rel="noopener noreferrer" className="btn-icon" title="打开原文">
              <ExternalLink size={12} />
            </a>
          )}
          <span className="chip">{item.language ?? "?"}</span>
          {item.category && <span className="chip chip--blue">{item.category}</span>}
          {item.tags?.map((t) => (
            <span key={t.id} className="chip chip--pink" title={`${t.namespace}:${t.value}`}>{t.value}</span>
          ))}
        </div>
      </div>
      {expanded && (
        <div className="item-card-body" id={`item-content-${item.id}`}>
          {item.summary && <p className="text-muted">{item.summary}</p>}
          {!item.summary && item.url && <p className="text-muted">URL: {item.url}</p>}
          <div className="item-card-footer" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span className="text-muted small">
              {item.collected_at && `采集: ${new Date(item.collected_at).toLocaleString("zh")}`}
              {item.published_at && ` · 发布: ${new Date(item.published_at).toLocaleString("zh")}`}
              {` · 来源: ${item.source_id}`}
              {` · 质量: ${item.quality_score.toFixed(2)}`}
            </span>
            <button type="button" className="btn btn-sm btn-ghost" onClick={(e) => {
              e.stopPropagation();
              const parent = e.currentTarget.closest('.page');
              if (parent) {
                const app = parent.closest('.view-frame')?.querySelector('[data-reading-trigger]');
              }
            }}>
            </button>
          </div>
          <button type="button" className="btn btn-sm btn-secondary" style={{ marginTop: 8, width: "100%" }}
            onClick={(e) => {
              e.stopPropagation();
              // Find the reading modal trigger in the parent component
              const event = new CustomEvent('open-reading', { detail: item });
              window.dispatchEvent(event);
            }}>
            <BookOpenText size={14} /> 阅读全文
          </button>
        </div>
      )}
    </article>
  );
}
