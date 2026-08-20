import '@testing-library/jest-dom';

// jsdom implements no layout, so it ships no scrollIntoView. Components that
// keep a highlighted row in view (the searchable Select) call it on every
// keyboard move and would throw here for a reason that has nothing to do with
// the behaviour under test. A no-op is the right stand-in: there is no viewport
// to scroll.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function scrollIntoView() {};
}
