import type { ReactNode } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
  CollectionDetail,
  CollectionDetailTab,
} from "@/features/collections/collection-detail-types";
import styles from "./collection-detail.module.css";

type CollectionDetailTabsProps = {
  activeTab: CollectionDetailTab;
  children: ReactNode;
  collection: CollectionDetail;
  onTabChange: (tab: CollectionDetailTab) => void;
};

export function CollectionDetailTabs({
  activeTab,
  children,
  collection,
  onTabChange,
}: CollectionDetailTabsProps) {
  return (
    <Tabs
      className={styles.tabs}
      onValueChange={(value) => onTabChange(value as CollectionDetailTab)}
      value={activeTab}
    >
      <TabsList aria-label="Collection sections" className={styles.tabList}>
        <TabsTrigger
          aria-label={`Documents ${collection.documentTotal}`}
          className={styles.tab}
          value="documents"
        >
          <span>Documents</span>
          <span className={styles.tabCount}>{collection.documentTotal}</span>
        </TabsTrigger>
        <TabsTrigger
          aria-label={`History ${collection.questionTotal}`}
          className={styles.tab}
          value="history"
        >
          <span>History</span>
          <span className={styles.tabCount}>{collection.questionTotal}</span>
        </TabsTrigger>
      </TabsList>
      <TabsContent className={styles.tabContent} value="documents">
        {activeTab === "documents" ? children : null}
      </TabsContent>
      <TabsContent className={styles.tabContent} value="history">
        {activeTab === "history" ? children : null}
      </TabsContent>
    </Tabs>
  );
}
