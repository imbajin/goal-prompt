/*
 * Licensed to the Apache Software Foundation (ASF) under one or more
 * contributor license agreements.  See the NOTICE file distributed with
 * this work for additional information regarding copyright ownership.
 * The ASF licenses this file to You under the Apache License, Version 2.0.
 */

import org.junit.runner.JUnitCore;
import org.junit.runner.Request;
import org.junit.runner.Result;
import org.junit.runner.notification.Failure;

/** Runs one hidden JUnit 4 method without candidate Surefire or lifecycle hooks. */
public final class TrustedMethodRunner {

    private TrustedMethodRunner() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2) {
            throw new IllegalArgumentException("expected <class> <method>");
        }
        Result result = new JUnitCore().run(
                Request.method(Class.forName(args[0]), args[1]));
        for (Failure failure : result.getFailures()) {
            System.out.println(failure.toString());
            System.out.println(failure.getTrace());
        }
        if (result.wasSuccessful() && result.getRunCount() == 1) {
            System.out.println("HG_AB_TRUSTED_TEST_PASS:" + args[1]);
            return;
        }
        System.exit(1);
    }
}
