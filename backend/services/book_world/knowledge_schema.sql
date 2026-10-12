-- T05 index approved per-character projections; canonical rows remain immutable.
CREATE VIRTUAL TABLE IF NOT EXISTS book_claims_fts USING fts5(terms, tokenize='unicode61');
CREATE TRIGGER IF NOT EXISTS tr_book_views_fts_insert AFTER INSERT ON book_access_evidence
BEGIN
  INSERT INTO book_claims_fts(rowid,terms)
  SELECT new.rowid,book_search_terms(c.proposition || ' ' || new.approved_excerpt)
  FROM book_claims c WHERE c.book_id=new.book_id AND c.source_version_id=new.source_version_id AND c.build_id=new.build_id AND c.id=new.claim_id;
END;
CREATE TRIGGER IF NOT EXISTS tr_book_views_fts_update AFTER UPDATE OF approved_excerpt ON book_access_evidence
BEGIN
  DELETE FROM book_claims_fts WHERE rowid=old.rowid;
  INSERT INTO book_claims_fts(rowid,terms)
  SELECT new.rowid,book_search_terms(c.proposition || ' ' || new.approved_excerpt)
  FROM book_claims c WHERE c.book_id=new.book_id AND c.source_version_id=new.source_version_id AND c.build_id=new.build_id AND c.id=new.claim_id;
END;
CREATE TRIGGER IF NOT EXISTS tr_book_views_fts_delete AFTER DELETE ON book_access_evidence
BEGIN DELETE FROM book_claims_fts WHERE rowid=old.rowid; END;
CREATE TRIGGER IF NOT EXISTS tr_book_claims_fts_update AFTER UPDATE OF proposition ON book_claims
BEGIN
  DELETE FROM book_claims_fts WHERE rowid IN (SELECT rowid FROM book_access_evidence WHERE book_id=new.book_id AND source_version_id=new.source_version_id AND build_id=new.build_id AND claim_id=new.id);
  INSERT INTO book_claims_fts(rowid,terms)
  SELECT v.rowid,book_search_terms(new.proposition || ' ' || v.approved_excerpt)
  FROM book_access_evidence v WHERE v.book_id=new.book_id AND v.source_version_id=new.source_version_id AND v.build_id=new.build_id AND v.claim_id=new.id;
END;
INSERT OR REPLACE INTO book_claims_fts(rowid,terms)
SELECT v.rowid,book_search_terms(c.proposition || ' ' || v.approved_excerpt)
FROM book_access_evidence v JOIN book_claims c ON c.book_id=v.book_id AND c.source_version_id=v.source_version_id AND c.build_id=v.build_id AND c.id=v.claim_id;
