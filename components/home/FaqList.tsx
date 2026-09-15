import { FAQ } from "@/data/faq";

export function FaqList() {
  return (
    <section className="faq-section" id="faq" aria-labelledby="faq-h">
      <h2 className="section-label" id="faq-h">
        자주 묻는 질문
      </h2>
      {FAQ.map((item) => (
        <details key={item.q} className="faq-item">
          <summary>{item.q}</summary>
          <p className="ans">{item.a}</p>
        </details>
      ))}
    </section>
  );
}
