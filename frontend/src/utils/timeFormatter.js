export function formatTimeToggle(dateInput, timeZone, includeDate = true) {
  if (!dateInput) return '-';
  
  let d;
  if (dateInput instanceof Date) {
    d = dateInput;
  } else if (typeof dateInput === 'number') {
    d = new Date(dateInput);
  } else {
    let str = String(dateInput);
    if (!str.includes('Z') && !str.includes('+')) {
      if (str.includes(' ') || str.includes('T')) {
        str += 'Z'; // Append Z to standard database strings to force UTC parsing
      }
    }
    d = new Date(str);
  }

  const isLocal = timeZone === 'Local';
  const options = {
    timeZone: isLocal ? undefined : timeZone,
    hour12: true,
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit'
  };

  if (includeDate) {
    options.year = 'numeric';
    options.month = 'numeric';
    options.day = 'numeric';
  }

  try {
    const formatted = d.toLocaleString('en-US', options);
    // Determine suffix
    let suffix = '';
    if (timeZone === 'America/New_York') suffix = ' ET';
    else if (timeZone === 'Europe/London') suffix = ' GMT';
    else if (timeZone === 'Asia/Tokyo') suffix = ' JST';
    else if (timeZone === 'Asia/Ho_Chi_Minh') suffix = ' ICT';
    else if (!isLocal) suffix = ' ' + timeZone;

    return formatted + suffix;
  } catch (e) {
    return d.toLocaleString() + ' (Error)';
  }
}
