import styles from "./collection-detail.module.css";

type CollectionSectionHeaderProps = {
  countLabel: string;
  title: string;
};

export function CollectionSectionHeader({
  countLabel,
  title,
}: CollectionSectionHeaderProps) {
  return (
    <div className={styles.sectionHeader}>
      <h2>{title}</h2>
      <p>{countLabel}</p>
    </div>
  );
}
