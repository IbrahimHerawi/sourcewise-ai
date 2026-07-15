import styles from "./dashboard-page-header.module.css";

interface DashboardPageHeaderProps {
  id: string;
  title: string;
}

export function DashboardPageHeader({ id, title }: DashboardPageHeaderProps) {
  return (
    <header className={styles.header}>
      <h1 className={styles.title} id={id}>
        {title}
      </h1>
    </header>
  );
}
