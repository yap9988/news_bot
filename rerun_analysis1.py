import logging
import config
import time
from database import DatabaseManager, Article
from notifier import Notifier

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def backfill():
    logger.info("Starting Backfill/Rerun Process (Batch: 100 records)...")
    db = DatabaseManager(config.DATABASE_URL)
    notifier = Notifier(config)
    session = db.session
    
    try:
        # Target records that are missing AI analysis or showing defaults
        articles = session.query(Article).filter(
            Article.is_deleted == False
        ).filter(
            (Article.instruments == None) | (Article.instruments == 'N/A') | (Article.instruments == '') |
            (Article.cause == None) | (Article.cause == '') |
            (Article.effect == None) | (Article.effect == '')
        ).limit(100).all()
        
        total = len(articles)
        if total == 0:
            logger.info("No records found needing analysis. Everything looks complete!")
            return

        logger.info(f"Found {total} records to process in this batch.")

        for i, art in enumerate(articles):
            logger.info(f"[{i+1}/{total}] Analyzing: {art.title[:60]}...")
            
            try:
                # Perform Professional AI Analysis
                inst, cause, effect = notifier.analyze_article_cause_effect(art.title, art.summary)
                
                # Update the record directly in the articles table
                art.instruments = inst
                art.cause = cause
                art.effect = effect
                art.processed = True
                session.commit()
                
                # Safety sleep to stay under 20 RPM (approx 17 per minute)
                time.sleep(3.5)
                
            except Exception as e:
                logger.error(f"Failed to analyze article {art.id}: {e}")
                session.rollback()
                continue

        logger.info("--- BATCH COMPLETE ---")
        logger.info("100 records updated. Run again for the next batch.")

    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    backfill()
