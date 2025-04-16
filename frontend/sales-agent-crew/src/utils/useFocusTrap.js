import { customRef } from 'vue';

// HTML elements that we want to be focusable.
const focusableElementsSelector =
  'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

const useFocusTrap = () => {
  let focusableElements = [];
  let $firstFocusable;
  let $lastFocusable;
  const trapRef = customRef((track, trigger) => {
    let $trapEl = null;
    return {
      get() {
        track();
        return $trapEl;
      },
      set(value) {
        $trapEl = value;
        value ? initFocusTrap() : clearFocusTrap();
        trigger();
      },
    };
  });

  // Check which key was pressed and handle multiple scenarios.
  function keyHandler(e) {
    const isTabPressed = e.key === 'Tab';

    // If the key pressed is not Tab, bail out of the function.
    if (!isTabPressed) return;

    if (e.shiftKey) {
      // If the shift key is also pressed and the element focused is the first one, jump to the last one.
      if (document.activeElement === $firstFocusable) {
        $lastFocusable.focus();
        e.preventDefault();
      }
      // Else, the element focused is the last one, jump to the last element.
    } else {
      if (document.activeElement === $lastFocusable) {
        $firstFocusable.focus();
        e.preventDefault();
      }
    }
  }

  function initFocusTrap() {
    // Bail out if there is no value
    if (!trapRef.value) return;
    focusableElements = trapRef.value.querySelectorAll(
      focusableElementsSelector
    );
    $firstFocusable = focusableElements[0];
    $lastFocusable = focusableElements[focusableElements.length - 1];
    document.addEventListener('keydown', keyHandler);
    $firstFocusable.focus();
  }

  function clearFocusTrap() {
    document.removeEventListener('keydown', keyHandler);
  }

  return {
    trapRef,
    initFocusTrap,
    clearFocusTrap,
  };
};

export default useFocusTrap;
