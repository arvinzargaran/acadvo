import { Link } from 'react-router';
import { LegalPage, Section } from '../legal/LegalPage';
import {
  GOVERNING_PROVINCE,
  LAST_UPDATED,
  MINIMUM_AGE,
  privacyEmail,
} from '../legal/config';

/**
 * Terms of use.
 *
 * The section that actually matters is "Not academic advice". Everything else
 * here is ordinary boilerplate; that one is the honest description of what this
 * product is, and the difference between a student who checks a generated plan
 * against their calendar and one who doesn't graduate on time because they
 * didn't.
 *
 * Deliberately not included: an arbitration clause, a class-action waiver, and a
 * unilateral "we may change these terms at any time, continued use is
 * acceptance" clause. They are common, they are enforceable in some places, and
 * for a free student tool they are not worth what they cost in trust — Ontario
 * consumer-protection law voids much of it against consumers anyway.
 */
export default function TermsPage() {
  const contact = privacyEmail();

  return (
    <LegalPage
      eyebrow="Terms"
      title="Terms of use"
      updated={LAST_UPDATED}
      summary="What you can expect from acadvo, and what it expects from you. The important part is section 3: this is a planning tool, not your academic advisor."
    >
      <Section id="agreement" heading="1. The agreement">
        <p>
          Using acadvo means agreeing to these terms. If you do not agree with them, do not create
          an account. They are an agreement between you and the individual in {GOVERNING_PROVINCE},
          Canada who operates the service (“acadvo”, “we”).
        </p>
      </Section>

      <Section id="eligibility" heading="2. Who can use it">
        <p>
          You must be at least {MINIMUM_AGE} years old and be, or be about to become, a
          post-secondary student. One account per person. You are responsible for what happens under
          your account, so keep your password to yourself and tell us at {contact} if you think
          someone else has it.
        </p>
      </Section>

      <Section id="not-advice" heading="3. This is not academic advice">
        <p className="font-medium" style={{ color: 'var(--wf-ink)' }}>
          acadvo is a planning tool. It is not your university, not your academic advisor, and not
          affiliated with any institution. Nothing it produces is an official statement of your
          degree progress, your eligibility to graduate, or your standing in a program.
        </p>
        <p>
          Course catalogues, prerequisites, and requirement rules change, are worded ambiguously,
          and differ by program, year of entry, and exception. Some of the data here is read
          automatically from public university pages, and some is inferred by an AI model — both can
          be out of date, incomplete, or simply wrong. GPA and progress figures are computed from
          what you entered, which may itself be wrong.
        </p>
        <p>
          <strong>Before you act on anything acadvo tells you</strong> — enrolling, dropping,
          choosing a specialization, believing you are on track to graduate — confirm it against
          your institution’s official calendar and with a real academic advisor. Where acadvo and
          your university disagree, your university is right. Decisions you make from acadvo’s
          output, and their academic consequences, are yours.
        </p>
      </Section>

      <Section id="ai" heading="4. AI features">
        <p>
          The advisor, planner, document parsing, and résumé review are powered by a third-party
          language model. Output is generated, not retrieved: it can be confidently wrong, can
          invent a course that does not exist, and will not be identical twice. Treat it as a
          well-read first draft, never as a source of truth. How your data is handled by that
          provider is described in the <Link to="/privacy" className="underline">Privacy Policy</Link>.
        </p>
        <p>
          The résumé review and career guidance are likewise informational. They are not employment,
          immigration, financial, or legal advice.
        </p>
      </Section>

      <Section id="your-content" heading="5. Your content">
        <p>
          Your transcript, your grades, your projects, and everything else you put into acadvo
          remain yours. You grant only the permission needed to run the service for you: to store
          it, process it, display it back to you, and send the relevant parts to the AI provider
          when you use an AI feature. That permission ends when you delete the content or your
          account.
        </p>
        <p>
          Only upload documents you have the right to upload. Do not upload another person’s
          transcript, or material you are not permitted to share.
        </p>
      </Section>

      <Section id="acceptable-use" heading="6. Acceptable use">
        <p>Do not:</p>
        <ul className="list-disc pl-5 space-y-1.5">
          <li>attempt to access another user’s account or data;</li>
          <li>probe, scan, or attack the service, or work around rate limits, quotas, or the verification requirement;</li>
          <li>scrape the service, or use it to build a competing dataset;</li>
          <li>use it to cheat — to complete graded work, to sit an assessment, or in any way your institution’s academic integrity policy forbids;</li>
          <li>upload malware, or content that is unlawful or infringing;</li>
          <li>resell or redistribute the service.</li>
        </ul>
        <p>
          Security research is welcome when it is done responsibly and reported to {contact} — see
          the disclosure policy in the project’s SECURITY document.
        </p>
      </Section>

      <Section id="availability" heading="7. Availability">
        <p>
          acadvo is free and provided as-is. There is no uptime guarantee, no support commitment,
          and features can change or be withdrawn. AI features depend on a third-party provider and
          on a quota; when that quota is exhausted or the provider is down, those features stop
          working until it recovers. Keep your own copy of anything you cannot afford to lose —{' '}
          <em>Download my data</em> in Settings exists for exactly that.
        </p>
      </Section>

      <Section id="termination" heading="8. Ending it">
        <p>
          You can delete your account at any time from Settings; it and everything in it are removed
          immediately and permanently. We may suspend or close an account that breaks section 6, or
          stop operating the service altogether — in which case you will be given reasonable notice
          and a chance to export your data first, unless circumstances make that impossible.
        </p>
      </Section>

      <Section id="liability" heading="9. Warranties and liability">
        <p>
          The service is provided “as is” and “as available”, without warranties of any kind, express
          or implied, including any implied warranty of merchantability, fitness for a particular
          purpose, accuracy, or non-infringement. In particular, no warranty is made that course
          data, requirement rules, or AI output are accurate or current.
        </p>
        <p>
          To the extent the law allows, acadvo is not liable for indirect, incidental, special, or
          consequential damages, or for lost academic opportunity, delayed graduation, tuition costs,
          or lost data. Where liability cannot be excluded, it is limited to CAD $100 — the service
          is free, so there is no fee to refund.
        </p>
        <p>
          Nothing in these terms removes rights you have under {GOVERNING_PROVINCE}’s consumer
          protection legislation or any other law that cannot be waived by agreement. If a court
          finds a provision unenforceable, the rest stays in force.
        </p>
      </Section>

      <Section id="law" heading="10. Governing law">
        <p>
          These terms are governed by the laws of {GOVERNING_PROVINCE} and the federal laws of
          Canada that apply there, and the courts of {GOVERNING_PROVINCE} have jurisdiction over any
          dispute. Nothing here prevents you from bringing a claim in the province where you live if
          the law gives you that right.
        </p>
      </Section>

      <Section id="changes" heading="11. Changes">
        <p>
          If these terms change materially, you will be told in the app before the change takes
          effect, and you can close your account if you disagree. The date at the top always reflects
          the current version.
        </p>
      </Section>

      <Section id="contact" heading="12. Contact">
        <p>
          Questions about these terms: <a className="underline" href={`mailto:${contact}`}>{contact}</a>.
        </p>
      </Section>
    </LegalPage>
  );
}
