// src/utils/globalFunctions.js
export function formattedDuration(duration) {
    if (typeof duration !== 'number' || isNaN(duration)) return duration;
    if (duration < 60) {
      return duration.toFixed(2) + "s";
    } else {
      const minutes = Math.floor(duration / 60);
      const seconds = duration % 60;
      return `${minutes}m ${seconds.toFixed(2)}s`;
    }
  }
  
  export function isNumeric(val) {
    return !isNaN(Number(val));
  }