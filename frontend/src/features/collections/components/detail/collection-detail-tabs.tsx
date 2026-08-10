import type { ReactNode } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
  CollectionDetailTab,
} from "@/features/collections/collection-detail-types";
import styles from "./collection-detail.module.css";

type CollectionDetailTabsProps = {
  activeTab: CollectionDetailTab;
  children: ReactNode;
  documentTotal: number;
  onTabChange: (tab: CollectionDetailTab) => void;
  questionTotal: number;
};

export function CollectionDetailTabs({
  activeTab,
  children,
  documentTotal,
  onTabChange,
  questionTotal,
}: CollectionDetailTabsProps) {
  return (
    <Tabs
      className={styles.tabs}
      onValueChange={(value) => onTabChange(value as CollectionDetailTab)}
      value={activeTab}
    >
      <TabsList aria-label="Collection sections" className={styles.tabList}>
        <TabsTrigger
          aria-label={`Documents ${documentTotal}`}
          className={styles.tab}
          value="documents"
        >
          <span>Documents</span>
          <span className={styles.tabCount}>{documentTotal.toLocaleString()}</span>
        </TabsTrigger>
        <TabsTrigger
          aria-label={`History ${questionTotal}`}
          className={styles.tab}
          value="history"
        >
          <span>History</span>
          <span className={styles.tabCount}>{questionTotal.toLocaleString()}</span>
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
