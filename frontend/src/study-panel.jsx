import { createElement } from 'react';

export function StudyPanel({ html }) {
  return createElement('div', {
    dangerouslySetInnerHTML: { __html: html },
  });
}
