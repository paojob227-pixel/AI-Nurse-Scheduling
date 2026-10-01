type PageGuideProps = {
  purpose: string;
  steps: string[];
  note?: string;
  compact?: boolean;
};

export default function PageGuide({ purpose, steps, note, compact = false }: PageGuideProps): JSX.Element {
  return <section className={`page-guide${compact ? " compact" : ""}`} aria-label="คำแนะนำการใช้งานหน้านี้">
    <span className="page-guide-icon" aria-hidden="true">?</span>
    <div className="page-guide-content">
      <p className="page-guide-label">หน้านี้ใช้ทำอะไร</p>
      <p className="page-guide-purpose">{purpose}</p>
      <p className="page-guide-label">วิธีใช้งาน</p>
      <ol className="page-guide-steps">{steps.map(step => <li key={step}>{step}</li>)}</ol>
      {note && <p className="page-guide-note"><strong>หมายเหตุ:</strong> {note}</p>}
    </div>
  </section>;
}
