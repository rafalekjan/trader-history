export const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export const pad2 = (n: number) => String(n).padStart(2, "0");

/** "YYYY-MM-DD" from numeric parts (month is 1-based). */
export const isoDate = (year: number, month: number, day: number) =>
  `${year}-${pad2(month)}-${pad2(day)}`;
