/*
 * Licensed to the Apache Software Foundation (ASF) under one or more
 * contributor license agreements.  See the NOTICE file distributed with
 * this work for additional information regarding copyright ownership.
 * The ASF licenses this file to You under the Apache License, Version 2.0.
 */

package org.apache.hugegraph.store.core;

import static org.apache.hugegraph.store.constant.HugeServerTables.TABLES_MAP;
import static org.apache.hugegraph.store.constant.HugeServerTables.VERTEX_TABLE;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import org.apache.hugegraph.store.business.BusinessHandler;
import org.apache.hugegraph.store.business.BusinessHandlerImpl;
import org.apache.hugegraph.store.grpc.common.Key;
import org.apache.hugegraph.store.grpc.common.OpType;
import org.apache.hugegraph.store.grpc.session.BatchEntry;
import org.apache.hugegraph.store.meta.PartitionManager;
import org.apache.hugegraph.store.options.HgStoreEngineOptions;
import org.apache.hugegraph.store.options.RaftRocksdbOptions;
import org.apache.hugegraph.store.pd.FakePdServiceProvider;
import org.apache.hugegraph.store.pd.PdProvider;
import org.junit.AfterClass;
import org.junit.Assert;
import org.junit.BeforeClass;
import org.junit.Test;

import com.alipay.sofa.jraft.util.StorageOptionsFactory;
import com.google.protobuf.ByteString;

/**
 * Trusted black-box tests injected only into the isolated oracle copy.
 *
 * The Agent never receives this file.  Every assertion uses the public
 * BusinessHandler transaction/read/truncate behavior over a real temporary
 * RocksDB instance and FakePD graph-id allocator.
 */
public class TrustedBatchGraphIsolationTest {

    private static final int PARTITION_ID = 0;
    private static final int KEY_CODE = 0;
    private static final byte[] SHARED_KEY = bytes("shared-key");

    private static Path databasePath;
    private static BusinessHandler handler;

    @BeforeClass
    public static void setup() throws IOException {
        databasePath = Files.createTempDirectory("hg-ab-batch-isolation-");

        Map<String, Object> rocksdbConfig = new HashMap<>();
        rocksdbConfig.put("rocksdb.write_buffer_size", "1048576");
        StorageOptionsFactory.releaseAllOptions();
        RaftRocksdbOptions.initRocksdbGlobalConfig(rocksdbConfig);
        BusinessHandlerImpl.initRocksdb(rocksdbConfig, null);

        HgStoreEngineOptions options = new HgStoreEngineOptions();
        options.setDataPath(databasePath.toString());
        options.setRaftPath(databasePath.toString());

        HgStoreEngineOptions.FakePdOptions fakePd =
                new HgStoreEngineOptions.FakePdOptions();
        fakePd.setPartitionCount(1);
        fakePd.setPeersList("127.0.0.1");
        fakePd.setStoreList("127.0.0.1");
        options.setFakePdOptions(fakePd);

        PdProvider pdProvider = new FakePdServiceProvider(fakePd);
        PartitionManager partitionManager = new PartitionManager(pdProvider, options) {
            @Override
            public String getDbDataPath(int partitionId, String dbName) {
                return databasePath.resolve("data").toString();
            }

            @Override
            public boolean hasPartition(String graphName, int partitionId) {
                return partitionId == PARTITION_ID;
            }

            @Override
            public List<Integer> getLeaderPartitionIds(String graph) {
                return Collections.singletonList(PARTITION_ID);
            }
        };
        handler = new BusinessHandlerImpl(partitionManager);
        handler.createTable("trusted-setup", PARTITION_ID, VERTEX_TABLE);
    }

    @AfterClass
    public static void teardown() {
        if (handler != null) {
            handler.closeAll();
        }
        if (databasePath != null) {
            try {
                Files.walk(databasePath)
                     .sorted(Comparator.reverseOrder())
                     .forEach(path -> {
                         try {
                             Files.deleteIfExists(path);
                         } catch (IOException ignored) {
                             // The disposable oracle container is removed after the probe.
                         }
                     });
            } catch (IOException ignored) {
                // The disposable oracle container is removed after the probe.
            }
        }
    }

    @Test
    public void testPutIsolation() {
        assertTwoGraphIsolation("put", OpType.OP_TYPE_PUT,
                                bytes("put-value-a"), bytes("put-value-b"));
    }

    @Test
    public void testMergeIsolation() {
        String first = graph("merge-a");
        String second = graph("merge-b");
        writeBatch(first, OpType.OP_TYPE_MERGE, longBytes(11L));
        Assert.assertNull("HG_AB_CROSS_GRAPH_LEAK: first MERGE became visible in second graph",
                          read(second));
        writeBatch(second, OpType.OP_TYPE_MERGE, longBytes(29L));
        Assert.assertEquals(11L, bytesLong(read(first)));
        Assert.assertEquals(29L, bytesLong(read(second)));
    }

    @Test
    public void testTruncateIsolation() {
        String first = graph("truncate-a");
        String second = graph("truncate-b");
        writeBatch(first, OpType.OP_TYPE_PUT, bytes("kept"));
        writeBatch(second, OpType.OP_TYPE_PUT, bytes("removed"));
        handler.truncate(second, PARTITION_ID);
        Assert.assertArrayEquals("HG_AB_CROSS_GRAPH_LEAK: truncating second graph changed first",
                                 bytes("kept"), read(first));
        Assert.assertNull(read(second));
    }

    @Test
    public void testRollbackRetry() {
        String graph = graph("rollback-retry");
        BatchEntry valid = batchEntry(OpType.OP_TYPE_PUT,
                                      TABLES_MAP.get(VERTEX_TABLE),
                                      bytes("never-visible"));
        BatchEntry invalid = batchEntry(OpType.OP_TYPE_PUT,
                                        Integer.MAX_VALUE,
                                        bytes("invalid-table"));
        try {
            handler.doBatch(graph, PARTITION_ID,
                            java.util.Arrays.asList(valid, invalid));
            Assert.fail("the invalid table must fail the whole batch");
        } catch (RuntimeException expected) {
            // The first PUT is already staged before the invalid second entry
            // forces BusinessHandler.doBatch() to roll the session back.
        }
        Assert.assertNull(read(graph));

        writeBatch(graph, OpType.OP_TYPE_PUT, bytes("retry-visible"));
        Assert.assertArrayEquals(bytes("retry-visible"), read(graph));
    }

    @Test
    public void testConcurrentFirstWrite() throws Exception {
        final int graphCount = 12;
        ExecutorService pool = Executors.newFixedThreadPool(graphCount);
        CountDownLatch ready = new CountDownLatch(graphCount);
        CountDownLatch start = new CountDownLatch(1);
        List<String> graphs = new ArrayList<>();
        List<byte[]> values = new ArrayList<>();
        List<Future<?>> futures = new ArrayList<>();
        try {
            for (int i = 0; i < graphCount; i++) {
                String graph = graph("concurrent-" + i);
                byte[] value = bytes("concurrent-value-" + i);
                graphs.add(graph);
                values.add(value);
                futures.add(pool.submit(() -> {
                    ready.countDown();
                    Assert.assertTrue(start.await(10, TimeUnit.SECONDS));
                    writeBatch(graph, OpType.OP_TYPE_PUT, value);
                    return null;
                }));
            }
            Assert.assertTrue("workers did not become ready",
                              ready.await(10, TimeUnit.SECONDS));
            start.countDown();
            for (Future<?> future : futures) {
                future.get(30, TimeUnit.SECONDS);
            }
            for (int i = 0; i < graphCount; i++) {
                Assert.assertArrayEquals("graph " + graphs.get(i),
                                         values.get(i), read(graphs.get(i)));
            }
        } finally {
            start.countDown();
            pool.shutdownNow();
            Assert.assertTrue("executor did not terminate",
                              pool.awaitTermination(10, TimeUnit.SECONDS));
        }
    }

    @Test
    public void testCompatibilityWithAllocatedGraphId() {
        String graph = graph("existing-id");
        ((BusinessHandlerImpl) handler).getKeyCreator()
                                       .getGraphIdOrCreate(PARTITION_ID, graph);
        writeBatch(graph, OpType.OP_TYPE_PUT, bytes("stable-format"));
        assertTwoGraphIsolation("after-existing", OpType.OP_TYPE_PUT,
                                bytes("new-a"), bytes("new-b"));
        Assert.assertArrayEquals(bytes("stable-format"), read(graph));
    }

    private static void assertTwoGraphIsolation(String prefix, OpType type,
                                                byte[] firstValue,
                                                byte[] secondValue) {
        String first = graph(prefix + "-a");
        String second = graph(prefix + "-b");
        writeBatch(first, type, firstValue);
        Assert.assertNull("HG_AB_CROSS_GRAPH_LEAK: first write became visible in second graph",
                          read(second));
        writeBatch(second, type, secondValue);
        Assert.assertArrayEquals(firstValue, read(first));
        Assert.assertArrayEquals(secondValue, read(second));
    }

    private static void writeBatch(String graph, OpType type, byte[] value) {
        BatchEntry entry = batchEntry(type, TABLES_MAP.get(VERTEX_TABLE), value);
        handler.doBatch(graph, PARTITION_ID, Collections.singletonList(entry));
    }

    private static BatchEntry batchEntry(OpType type, int table, byte[] value) {
        Key key = Key.newBuilder()
                     .setCode(KEY_CODE)
                     .setKey(ByteString.copyFrom(SHARED_KEY))
                     .build();
        BatchEntry entry = BatchEntry.newBuilder()
                                     .setOpType(type)
                                     .setTable(table)
                                     .setStartKey(key)
                                     .setValue(ByteString.copyFrom(value))
                                     .build();
        return entry;
    }

    private static byte[] read(String graph) {
        return handler.doGet(graph, KEY_CODE, VERTEX_TABLE, SHARED_KEY);
    }

    private static String graph(String suffix) {
        return "hg-ab-" + suffix;
    }

    private static byte[] bytes(String value) {
        return value.getBytes(StandardCharsets.UTF_8);
    }

    private static byte[] longBytes(long value) {
        return ByteBuffer.allocate(Long.BYTES)
                         .order(ByteOrder.LITTLE_ENDIAN)
                         .putLong(value)
                         .array();
    }

    private static long bytesLong(byte[] value) {
        Assert.assertNotNull(value);
        return ByteBuffer.wrap(value)
                         .order(ByteOrder.LITTLE_ENDIAN)
                         .getLong();
    }
}
