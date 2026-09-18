import { Link } from 'react-router';
import { DataTable, LegalPage, Section } from '../legal/LegalPage';
import {
  GOVERNING_PROVINCE,
  HOSTING_REGION,
  LAST_UPDATED,
  MINIMUM_AGE,
  privacyEmail,
} from '../legal/config';

/**
 * Privacy policy.
 *
 * Structured against PIPEDA's ten fair information principles, and specifically
 * against Principle 8 (Openness) 4.8.2, which requires that the accountable
 * person's contact, the means of access, and a description of what is held with
 * a general account of its use all be readily available.
 *
 * Every factual claim here was checked against the code, not written from a
 * template: the retention rules match what the delete cascade actually does, the
 * "we don't store your uploads" claim matches routers/career.py and
 * routers/degree.py (bytes are parsed in memory and dropped), and the Groq
 * description matches Groq's published data policy. If any of those change, this
 * page is wrong and has to change with them.
 */
export default function PrivacyPage() {
  const contact = privacyEmail();

  return (
    <LegalPage
      eyebrow="Privacy"
      title="Privacy policy"
      updated={LAST_UPDATED}
      summary="acadvo holds your transcript, your grades, and what you tell the advisor. This page says exactly what is collected, who else sees it, how long it is kept, and how to get a copy or delete all of it."
    >
      <Section id="short-version" heading="The short version">
        <ul className="list-disc pl-5 space-y-1.5">
          <li>Your academic record is stored so the app can plan around it. It is not sold, rented, or used for advertising — there is no advertising here.</li>
          <li>There are no analytics, no tracking pixels, and no third-party cookies. The only cookies are the two that keep you signed in.</li>
          <li>Uploaded documents (transcripts, checklists, résumés) are read and then discarded. What is kept is the courses and grades extracted from them.</li>
          <li>AI features send the relevant part of your record to Groq, in the United States, to generate a response. Groq does not train on it.</li>
          <li>You can download everything held about you, or delete your account and all of it, from Settings, at any time, without asking anyone.</li>
        </ul>
      </Section>

      <Section id="who" heading="1. Who is responsible for your information">
        <p>
          acadvo is operated by an individual in {GOVERNING_PROVINCE}, Canada, who is the person
          accountable for the personal information it holds. Privacy questions, access requests,
          corrections, and complaints go to <a className="underline" href={`mailto:${contact}`}>{contact}</a>.
        </p>
        <p>
          Because acadvo is not affiliated with, endorsed by, or operating on behalf of any
          university, your institution has no access to your acadvo account, and nothing you record
          here reaches your academic file.
        </p>
      </Section>

      <Section id="what" heading="2. What is collected, why, and for how long">
        <DataTable
          rows={[
            {
              what: 'Email address and name',
              why: 'To identify your account, verify that the address is yours, and send password resets. Never used for marketing.',
              kept: 'You delete the account',
            },
            {
              what: 'Password',
              why: 'Stored only as a bcrypt hash. The original is never written down and cannot be recovered — only reset.',
              kept: 'You delete the account',
            },
            {
              what: 'University, program, start and expected graduation year, optionally country and city',
              why: 'To pick the right course catalogue and requirement rules, and to place courses in the right terms.',
              kept: 'You delete the account',
            },
            {
              what: 'Courses, credits, grades, assessment weights and scores',
              why: 'The core of the product: GPA tracking, requirement progress, and course recommendations are computed from these.',
              kept: 'You delete them, or delete the account',
            },
            {
              what: 'Uploaded transcripts, degree checklists, syllabi and résumés',
              why: 'Read once to extract courses, grades, and deadlines, or to generate a résumé review. The file itself is never written to disk or to the database — only the extracted records are kept.',
              kept: 'Not stored at all',
            },
            {
              what: 'Projects, milestones, career targets, practice problems, study sessions',
              why: 'Features you choose to use; each is stored so it is still there next time.',
              kept: 'You delete them, or delete the account',
            },
            {
              what: 'Conversations with the AI advisor',
              why: 'So a conversation has history and can be reopened.',
              kept: 'You delete the conversation, or delete the account',
            },
            {
              what: 'IP address',
              why: 'Used transiently to rate-limit requests and to slow down password guessing. It is a key in an in-memory store, not a record attached to you.',
              kept: 'Rate-limit window (hours), plus web server access logs',
            },
            {
              what: 'Error reports',
              why: 'When a server error occurs, a report may be sent to an error-tracking service so it can be fixed. It is configured to exclude personal data and to strip your calendar token.',
              kept: 'Per the error tracker’s retention, if enabled at all',
            },
          ]}
        />
        <p>
          Nothing above is collected for a purpose other than the one stated. If that ever changes,
          you will be asked first — a new purpose needs new consent.
        </p>
      </Section>

      <Section id="ai" heading="3. What happens when you use an AI feature">
        <p>
          The advisor, the semester planner, document parsing, and the résumé review all work by
          sending a prompt to <strong>Groq</strong>, an inference provider in the United States.
          That prompt contains the part of your record the feature needs — for the planner, your
          completed courses and requirement buckets; for a résumé review, the text or image of the
          document you uploaded; for the advisor, your name, so it can address you. Your email
          address and password are never sent.
        </p>
        <p>
          Per Groq’s published data policy, inputs and outputs are not used to train models, and are
          not retained by default; they may be logged for up to 30 days only when investigating a
          platform error or suspected abuse. Because that processing happens in the United States,
          the information is subject to lawful access by US courts and authorities while it is
          there. That is an unavoidable consequence of using a US provider, and it is the reason
          this paragraph exists rather than being buried.
        </p>
        <p>
          AI output is generated text. It can be wrong, and it is not academic advice — see the{' '}
          <Link to="/terms" className="underline">Terms of Use</Link>.
        </p>
      </Section>

      <Section id="sharing" heading="4. Who else your information reaches">
        <p>Only these, and only to run the service:</p>
        <ul className="list-disc pl-5 space-y-1.5">
          <li><strong>Groq (United States)</strong> — AI inference, as described above.</li>
          <li><strong>An email provider</strong> — to deliver verification and password-reset messages. It receives your email address and the message.</li>
          <li><strong>The hosting provider</strong> — the servers in {HOSTING_REGION} where the database runs.</li>
          <li><strong>An error-tracking service</strong> — only if enabled, and configured not to send personal data.</li>
        </ul>
        <p>
          One more recipient exists only if you choose it: subscribing to the calendar feed hands
          your course names and deadlines to whichever calendar you subscribe from (Google, Apple,
          Microsoft), on their terms rather than ours. The feed link is a password in URL form —
          anyone holding it can read that calendar — so treat it like one, and reset it from
          Settings if it gets out.
        </p>
        <p>
          Your information is not sold, rented, traded, or given to advertisers, data brokers, or
          your university. It would only be disclosed otherwise if the law required it — a court
          order or a valid legal demand — or to protect someone from imminent harm.
        </p>
      </Section>

      <Section id="location" heading="5. Where your information is stored">
        <p>
          The database — your account, courses, grades, projects, and conversations — is hosted in{' '}
          {HOSTING_REGION}. The exception is the AI processing described in section 3, which happens
          in the United States at the moment you use an AI feature.
        </p>
      </Section>

      <Section id="security" heading="6. How it is protected">
        <ul className="list-disc pl-5 space-y-1.5">
          <li>All traffic is encrypted in transit (HTTPS, with HSTS).</li>
          <li>Passwords are stored as bcrypt hashes, never in a readable form.</li>
          <li>Session cookies are HTTP-only, so page scripts cannot read them, and are restricted to this site.</li>
          <li>Every query for your data is scoped to your account; this is enforced in code and covered by automated tests that fail the build if a route stops checking.</li>
          {/* Was "every endpoint is rate-limited", which two independent audits
              found false — 23 of 85 routes carry a limit and the limiter sets no
              default. An overstated security claim in a published policy is the
              kind of sentence a regulator reads back to you, so it says what the
              code does. */}
          <li>Repeated failed logins lock the account temporarily, and the endpoints that sign you in, cost money, or accept documents are rate-limited.</li>
          <li>The database is not reachable from the public internet.</li>
        </ul>
        <p>
          No system is perfectly secure. If a breach ever creates a real risk of significant harm to
          you, you will be told, and the Office of the Privacy Commissioner of Canada will be
          notified, as PIPEDA requires.
        </p>
      </Section>

      <Section id="rights" heading="7. Your rights, and how to use them">
        <ul className="list-disc pl-5 space-y-1.5">
          <li>
            <strong>Get a copy.</strong> Settings → <em>Download my data</em> produces a JSON file
            containing everything stored about your account. Nobody has to approve it. Security
            credentials — your password hash and your calendar token — are marked as withheld rather
            than included, because handing those out in a file would be a way to take over your own
            account.
          </li>
          <li><strong>Correct it.</strong> Anything wrong can be edited in the app directly; if something cannot be, write to {contact}.</li>
          <li>
            <strong>Delete it.</strong> Settings → <em>Delete account</em>, confirmed with your
            password. This removes the account and every record attached to it — courses, grades,
            projects, conversations, everything — immediately and permanently. It is not a
            deactivation and there is no recovery window.
          </li>
          <li><strong>Withdraw consent.</strong> You can stop using an AI feature at any time, or delete the account entirely. Some data is needed to provide the service at all, so withdrawing consent for it means closing the account.</li>
          <li><strong>Complain.</strong> Write to {contact} first. If the answer does not satisfy you, you can complain to the Office of the Privacy Commissioner of Canada at <a className="underline" href="https://www.priv.gc.ca" target="_blank" rel="noreferrer noopener">
              priv.gc.ca<span className="sr-only"> (opens in a new tab)</span>
            </a>.</li>
        </ul>
      </Section>

      <Section id="cookies" heading="8. Cookies">
        <p>
          Two cookies, both strictly necessary: <code className="wf-code">access_token</code> and{' '}
          <code className="wf-code">refresh_token</code>, which keep you signed in. Both are
          HTTP-only and same-site. There are no analytics cookies, no advertising cookies, and no
          third-party cookies — which is why this site has no cookie banner. Your browser’s local
          storage also holds a few conveniences that never reach the server: your theme, your
          practice-problem tracker, a cached copy of your weekly check-in, and whether you have seen
          the tour. Signing out clears them.
        </p>
      </Section>

      <Section id="minors" heading="9. Age">
        <p>
          acadvo is for post-secondary students and requires you to be at least {MINIMUM_AGE}. It is
          not directed at children, and information is not knowingly collected from anyone under
          that age. If you believe a minor has created an account, write to {contact} and it will be
          deleted.
        </p>
      </Section>

      <Section id="changes" heading="10. Changes to this policy">
        <p>
          If this policy changes in a way that affects what is collected or who sees it, the change
          will be announced in the app before it takes effect — not applied quietly to information
          already collected under the old terms. The date at the top always reflects the current
          version.
        </p>
      </Section>
    </LegalPage>
  );
}
