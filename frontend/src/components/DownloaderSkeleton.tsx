/** Reserve space without painting a large LCP candidate box. */
export function DownloaderSkeleton() {
  return (
    <div
      className="min-h-[12rem]"
      aria-busy="true"
      aria-label="載入介面中"
    />
  );
}
