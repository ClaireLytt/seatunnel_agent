import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

// Aceternity UI components rely on this helper.
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
