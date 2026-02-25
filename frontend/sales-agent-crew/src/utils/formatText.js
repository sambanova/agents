export function formattedText(data) {
  // Remove any trailing JSON block starting with "```json"
  const cleanedData = data.trim();

  const text = cleanedData || '';
  const lines = text.split('\n');
  let html = '';
  let inList = false;
  // Match bullet lines starting with *, +, or -
  const bulletRegex = /^([*+-])\s+(.*)/;
  const urlRegex = /^(.+?)\s*:\s*(https?:\/\/\S+)$/;

  lines.forEach((line) => {
    const trimmed = line.trim();
    const bulletMatch = trimmed.match(bulletRegex);

    if (bulletMatch) {
      if (!inList) {
        html += "<ul class='my-2'>";
        inList = true;
      }

      let bulletLine = bulletMatch[2];
      const urlMatch = bulletLine.match(urlRegex);

      // Check if it's a URL-like string.
      if (urlMatch) {
        const title = urlMatch[1].trim();
        const url = urlMatch[2].trim();

        // Only allow http/https URLs to prevent javascript: protocol injection
        if (url.startsWith('http://') || url.startsWith('https://')) {
          bulletLine = `<a href="${escapeHTML(url)}" target="_blank" rel="noopener noreferrer" class="underline">${escapeHTML(title)}</a>`;
        } else {
          bulletLine = escapeHTML(bulletLine);
        }
      } else {
        bulletLine = escapeHTML(bulletLine);
      }

      // Each bullet item gets an inline span for the bullet marker
      html += `<li class="custom-bullet overflow-hidden text-ellipsis mt-2"><span class="bullet-marker">•</span> ${bulletLine}</li>`;
    } else {
      if (inList) {
        html += '</ul>';
        inList = false;
      }

      // Check for the specific sentence
      if (
        trimmed.includes(
          "Please provide feedback on the following plan or type 'true' to approve it."
        )
      ) {
        // Format "provide feedback" and "type 'true'" in bold
        const escapedLine = escapeHTML(trimmed)
          .replace('provide feedback', '<strong>provide feedback</strong>')
          .replace("type &#039;true&#039;", "<strong>type 'true'</strong>");

        // Add a new line after this sentence
        html += `<p class="md-paragraph">${escapedLine}</p><br>`;
      } else if (trimmed.length > 0) {
        // If the line ends with a colon, treat it as a heading
        if (trimmed.endsWith(':')) {
          html += `<h2 class="md-heading text-[16px] font-semibold">${escapeHTML(trimmed)}</h2>`;
        } else {
          html += `<p class="md-paragraph">${escapeHTML(trimmed)}</p>`;
        }
      }
    }
  });

  if (inList) {
    html += '</ul>';
  }

  // Replace markdown bold syntax (i.e. **text**) with HTML <strong> tags.
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

  return html;
}

/**
 * Processes the input string by splitting it into segments:
 * - Any text inside <think> … </think> is rendered as markdown.
 * - Any JSON block wrapped in triple backticks (```json … ```) is parsed and rendered as a table.
 * - Any remaining text is rendered as markdown.
 *
 * Stray triple backticks are removed from the remaining text.
 */
export function renderMarkdownWithJSON(data) {
  if (!data) return '';
  let result = '';
  let remaining = data;

  // Process <think> block if present.
  const thinkRegex = /<think>([\s\S]*?)<\/think>/i;
  const thinkMatch = remaining.match(thinkRegex);
  if (thinkMatch) {
    const thinkContent = thinkMatch[1].trim();
    result += processMarkdown(thinkContent);
    remaining = remaining.replace(thinkRegex, '').trim();
  }

  // Process JSON blocks wrapped in triple backticks.
  const jsonRegex = /```json\s*([\s\S]*?)\s*```/gi;
  let match;

  while ((match = jsonRegex.exec(remaining)) !== null) {
    // Process text before this JSON block.
    const textBefore = remaining.slice(0, match.index);
    result += processMarkdown(textBefore);

    // Process the JSON block if it has nonempty content.
    if (match[1].trim()) {
      try {
        const jsonData = JSON.parse(match[1].trim());
        result += processJSON(jsonData);
      } catch (e) {
        console.error('Error parsing JSON block:', e);
        result += processMarkdown(match[0]);
      }
    }

    // Remove the processed portion from remaining text.
    remaining = remaining.slice(match.index + match[0].length);
    jsonRegex.lastIndex = 0; // Reset regex index after slicing.
  }

  // Remove any stray triple backticks from the remaining text.
  remaining = remaining.replace(/```/g, '').trim();

  // Optionally, check if any remaining text is pure JSON.
  const pureJSONMatch = remaining.match(/{[\s\S]*}/);
  if (pureJSONMatch && pureJSONMatch[0].trim()) {
    try {
      const jsonData = JSON.parse(pureJSONMatch[0].trim());
      result += processJSON(jsonData);
    } catch (e) {
      console.error('Error parsing pure JSON:', e);
      result += processMarkdown(pureJSONMatch[0]);
    }
    remaining = remaining.replace(/{[\s\S]*}/, '').trim();
  }

  // Process any remaining text as markdown.
  if (remaining) {
    result += processMarkdown(remaining);
  }

  return result;
}

/**
 * Renders plain text as markdown.
 * Each nonempty line is wrapped in a <p> tag.
 */
function processMarkdown(data) {
  const lines = data.split('\n').filter((line) => line.trim() !== '');
  let html = '';
  for (const line of lines) {
    html += `<p>${escapeHTML(line.trim())}</p>`;
  }
  return html;
}

/**
 * Renders a JSON object as an HTML table.
 * The table is styled with "display: inline-table; width: auto;" so it takes only as much width as needed.
 */
function processJSON(jsonData) {
  let html = '';
  const tableStyle =
    'display: inline-table; width: auto; border-collapse: separate; border-spacing: 0; border: 1px solid #EAECF0; border-radius: 8px; margin: 1em 0; font-family: Arial, sans-serif;';
  const cellStyle = 'padding: 8px; border-bottom: 1px solid #ddd;';
  const lastCellStyle = 'padding: 8px;';

  // Helper to add a row.
  const addRow = (key, value, isLast = false) => {
    const style = isLast ? lastCellStyle : cellStyle;
    html += `<tr>
      <td style="${cellStyle}; color:#101828;text-transform: capitalize;">${escapeHTML(
      key
    )}</td>
      <td style="${style}">${escapeHTML(String(value))}</td>
    </tr>`;
  };

  html += `<table style="${tableStyle}"><tbody>`;

  if (typeof jsonData === 'object' && jsonData !== null) {
    if (Array.isArray(jsonData)) {
      jsonData.forEach((item, idx) => {
        if (typeof item === 'object' && item !== null && !Array.isArray(item)) {
          const keys = Object.keys(item);
          keys.forEach((key, keyIdx) => {
            addRow(key, item[key], keyIdx === keys.length - 1);
          });
        } else {
          addRow(String(idx), item);
        }
      });
    } else {
      Object.keys(jsonData).forEach((key) => {
        const value = jsonData[key];
        if (
          typeof value === 'object' &&
          value !== null &&
          !Array.isArray(value)
        ) {
          Object.keys(value).forEach((innerKey, idx, arr) => {
            addRow(innerKey, value[innerKey], idx === arr.length - 1);
          });
        } else {
          addRow(key, value);
        }
      });
    }
  } else {
    html += `<tr><td colspan="2" style="${lastCellStyle}">${escapeHTML(
      String(jsonData)
    )}</td></tr>`;
  }

  html += `</tbody></table>`;
  return html;
}

/**
 * Escapes HTML special characters to prevent XSS and rendering issues.
 */
function escapeHTML(text) {
  if (typeof text !== 'string') return text;
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
