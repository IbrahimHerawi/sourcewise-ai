import type { Config } from "tailwindcss";
import tailwindcssAnimate from "tailwindcss-animate";

const config: Config = {
    darkMode: "class",
    content: [
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/features/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
  	extend: {
  		colors: {
			background: 'var(--sw-color-background-surface)',
			foreground: 'var(--sw-color-text-primary)',
			card: {
				DEFAULT: 'var(--sw-color-background-surface)',
				foreground: 'var(--sw-color-text-primary)'
			},
			popover: {
				DEFAULT: 'var(--sw-color-background-surface)',
				foreground: 'var(--sw-color-text-primary)'
			},
			primary: {
				DEFAULT: 'var(--sw-color-brand-default)',
				foreground: 'var(--sw-color-background-surface)'
			},
			secondary: {
				DEFAULT: 'var(--sw-color-background-surface-subtle)',
				foreground: 'var(--sw-color-text-primary)'
			},
			muted: {
				DEFAULT: 'var(--sw-color-background-surface-subtle)',
				foreground: 'var(--sw-color-text-secondary)'
			},
			accent: {
				DEFAULT: 'var(--sw-color-background-surface-subtle)',
				foreground: 'var(--sw-color-text-primary)'
			},
			destructive: {
				DEFAULT: 'var(--sw-color-status-destructive-foreground)',
				foreground: 'var(--sw-color-background-surface)'
			},
			border: 'var(--sw-color-border-default)',
			input: 'var(--sw-color-border-default)',
			ring: 'var(--sw-color-focus-ring)',
			chart: {
				'1': 'var(--color-chart-1)',
				'2': 'var(--color-chart-2)',
				'3': 'var(--color-chart-3)',
				'4': 'var(--color-chart-4)',
				'5': 'var(--color-chart-5)'
  			}
  		},
  		borderRadius: {
  			lg: 'var(--radius)',
  			md: 'calc(var(--radius) - 2px)',
  			sm: 'calc(var(--radius) - 4px)'
  		}
  	}
  },
  plugins: [tailwindcssAnimate],
};
export default config;
